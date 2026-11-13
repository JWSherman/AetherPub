import asyncio
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update, desc
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.event_bus import event_bus
from backend.app.models.entities import Source, Article, Keyword, DailyEdition, Setting, edition_articles
from backend.app.services.crawler.fetcher import create_http_client, polite_delay
from backend.app.services.crawler.discovery import DiscoveryService
from backend.app.services.extractor.readability import ReadabilityService
from backend.app.services.extractor.image_processor import ImageProcessor
from backend.app.services.curator.scorer import KeywordScorer
from backend.app.services.curator.simhash import are_near_duplicates
from backend.app.services.epub.generator import EPUBGenerator
from backend.app.services.delivery.smtp_client import SMTPDeliveryService

logger = logging.getLogger("aetherpub.pipeline")
scheduler = AsyncIOScheduler()

async def ingest_source(source_id: str):
    """Ingests fresh articles for a single source."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if not source or not source.is_active:
            return

        source.last_status = "crawling"
        await session.commit()

        await event_bus.emit("crawler:source_started", {"source_id": source.id, "name": source.name})

        # Fetch active keywords
        kw_res = await session.execute(select(Keyword))
        keywords = kw_res.scalars().all()

        # Fetch existing URLs and SimHashes for deduplication
        art_res = await session.execute(select(Article.url, Article.content_hash))
        existing_articles = art_res.all()
        existing_urls = {row[0] for row in existing_articles}
        existing_hashes = [row[1] for row in existing_articles]

        client = create_http_client()
        try:
            discovery = DiscoveryService(client)
            image_processor = ImageProcessor(client)

            candidates = await discovery.fetch_candidate_urls(source.base_url, source.feed_url)
            await event_bus.emit("crawler:candidates_found", {
                "source_id": source.id,
                "count": len(candidates)
            })

            ingested_count = 0
            for item in candidates:
                url = item.get("url")
                if not url or url in existing_urls:
                    continue

                await polite_delay(min_ms=150, max_ms=400)
                try:
                    resp = await client.get(url, timeout=12.0)
                    if resp.status_code != 200:
                        continue

                    # Extract readability
                    extracted = ReadabilityService.extract_article(resp.text, url)
                    if not extracted:
                        continue

                    # Deduplication check via SimHash
                    is_dup = any(are_near_duplicates(extracted["content_hash"], h) for h in existing_hashes)
                    if is_dup:
                        continue

                    # Score article against active keywords
                    score = KeywordScorer.score_article(extracted["title"], extracted["plain_text"], keywords)
                    if score < 0:
                        # Excluded by keyword
                        continue

                    pub_dt = None
                    raw_pub = extracted.get("published_at") or item.get("published")
                    if raw_pub:
                        if isinstance(raw_pub, datetime):
                            pub_dt = raw_pub
                        elif isinstance(raw_pub, str) and raw_pub.strip():
                            try:
                                from dateutil import parser
                                pub_dt = parser.parse(raw_pub)
                            except Exception:
                                pub_dt = None
                    if not pub_dt:
                        url_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
                        if url_match:
                            try:
                                year, month, day = map(int, url_match.groups())
                                pub_dt = datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
                            except Exception:
                                pub_dt = None
                    if not pub_dt:
                        pub_dt = datetime.now(timezone.utc)

                    new_article = Article(
                        source_id=source.id,
                        url=url,
                        title=extracted["title"],
                        author=extracted["author"],
                        published_at=pub_dt,
                        clean_html=extracted["clean_html"],
                        plain_text=extracted["plain_text"],
                        excerpt=extracted["excerpt"],
                        word_count=extracted["word_count"],
                        content_hash=extracted["content_hash"],
                        relevance_score=score,
                        is_bundled=False
                    )
                    session.add(new_article)
                    existing_urls.add(url)
                    existing_hashes.append(extracted["content_hash"])
                    ingested_count += 1

                    await event_bus.emit("article:ingested", {
                        "title": extracted["title"],
                        "source": source.name,
                        "score": score,
                        "word_count": extracted["word_count"]
                    })
                except Exception as e:
                    logger.warning(f"Failed to ingest article {url}: {e}")
                    continue

            source.last_status = "success"
            source.last_crawled_at = datetime.now(timezone.utc)
            source.error_message = None
            await session.commit()

            await event_bus.emit("crawler:source_completed", {
                "source_id": source.id,
                "name": source.name,
                "new_articles": ingested_count
            })
        except Exception as e:
            source.last_status = "error"
            source.error_message = str(e)
            await session.commit()
            await event_bus.emit("crawler:source_failed", {"source_id": source.id, "error": str(e)})
        finally:
            await client.aclose()

async def compile_daily_edition(limit: int | None = None) -> DailyEdition | None:
    """Compiles unbundled articles into a daily EPUB 3 edition."""
    async with AsyncSessionLocal() as session:
        # Load daily limit from settings if not specified
        if not limit:
            limit_setting = await session.execute(select(Setting).where(Setting.key == "DAILY_ARTICLE_LIMIT"))
            s_row = limit_setting.scalar_one_or_none()
            limit = int(s_row.value) if s_row else settings.DAILY_ARTICLE_LIMIT

        # Fetch top unbundled articles
        stmt = (
            select(Article)
            .where(Article.is_bundled == False)
            .order_by(desc(Article.relevance_score), desc(Article.created_at))
            .limit(limit)
        )
        result = await session.execute(stmt)
        articles = result.scalars().all()

        if not articles:
            await event_bus.emit("compiler:empty", {"message": "No unbundled articles available to compile."})
            return None

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await event_bus.emit("compiler:started", {"date": today_str, "article_count": len(articles)})

        # Prepare payload for generator
        prepared_articles = []
        client = create_http_client()
        image_processor = ImageProcessor(client)

        try:
            for art in articles:
                # Retrieve source name
                src_res = await session.execute(select(Source.name).where(Source.id == art.source_id))
                src_name = src_res.scalar_one_or_none() or "Web"

                # Reprocess images to get binaries
                clean_html, images = await image_processor.process_article_images(
                    art.clean_html,
                    article_id=art.id,
                    base_url=art.url
                )
                prepared_articles.append({
                    "id": art.id,
                    "title": art.title,
                    "author": art.author,
                    "url": art.url,
                    "source_name": src_name,
                    "word_count": art.word_count,
                    "clean_html": clean_html,
                    "images": images,
                    "published_at": art.published_at or art.created_at
                })
        finally:
            await client.aclose()

        # Build EPUB
        file_name = f"aetherpub_{today_str}_{datetime.now().strftime('%H%M%S')}.epub"
        epub_path = settings.EPUBS_DIR / file_name
        cover_path = settings.COVERS_DIR / f"{Path(file_name).stem}_cover.jpg"

        out_path, file_size = EPUBGenerator.build_daily_edition(
            date_str=today_str,
            articles=prepared_articles,
            output_path=epub_path,
            cover_output_path=cover_path
        )

        total_words = sum(a["word_count"] for a in prepared_articles)
        edition = DailyEdition(
            title=f"AetherPub Daily – {today_str}",
            edition_date=today_str,
            article_count=len(prepared_articles),
            total_word_count=total_words,
            file_path=str(out_path.resolve()),
            cover_path=str(cover_path.resolve()),
            file_size_bytes=file_size,
            sent_via_smtp=False
        )
        session.add(edition)
        await session.flush()

        # Mark articles as bundled and link to edition
        for idx, art in enumerate(articles):
            art.is_bundled = True
            await session.execute(
                edition_articles.insert().values(
                    edition_id=edition.id,
                    article_id=art.id,
                    chapter_order=idx + 1
                )
            )

        await session.commit()

        await event_bus.emit("compiler:completed", {
            "edition_id": edition.id,
            "title": edition.title,
            "article_count": edition.article_count,
            "file_size": file_size,
            "file_name": file_name
        })

        # Check for auto-send SMTP setting
        auto_smtp_res = await session.execute(select(Setting).where(Setting.key == "AUTO_SEND_SMTP"))
        auto_row = auto_smtp_res.scalar_one_or_none()
        if auto_row and auto_row.value.lower() == "true":
            kindle_res = await session.execute(select(Setting).where(Setting.key == "DEFAULT_KINDLE_EMAIL"))
            k_row = kindle_res.scalar_one_or_none()
            if k_row and k_row.value:
                try:
                    await SMTPDeliveryService.send_epub_email(
                        recipient_email=k_row.value,
                        epub_path=out_path,
                        edition_title=edition.title
                    )
                    edition.sent_via_smtp = True
                    await session.commit()
                    await event_bus.emit("smtp:sent", {"recipient": k_row.value, "edition_id": edition.id})
                except Exception as e:
                    logger.error(f"Auto-send SMTP failed: {e}")
                    await event_bus.emit("smtp:failed", {"error": str(e)})

        return edition

async def run_full_pipeline():
    """Runs ingestion across all active sources followed by compilation."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Source.id).where(Source.is_active == True))
        source_ids = result.scalars().all()

    for s_id in source_ids:
        await ingest_source(s_id)

    await compile_daily_edition()

def init_scheduler():
    scheduler.add_job(
        run_full_pipeline,
        trigger="cron",
        hour=settings.DAILY_CRON_HOUR,
        minute=settings.DAILY_CRON_MINUTE,
        id="aetherpub_daily_run",
        replace_existing=True
    )
    scheduler.start()
