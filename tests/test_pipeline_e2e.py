import pytest
import uuid
from pathlib import Path
from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.models.entities import Source, Keyword, Article, DailyEdition
from backend.app.services.scheduler.runner import compile_daily_edition

@pytest.mark.asyncio
async def test_full_compilation_pipeline():
    await init_db()

    test_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        # 1. Create a Source
        source = Source(
            name=f"Ars Technica {test_id}",
            base_url=f"https://arstechnica-{test_id}.com",
            feed_url=f"https://feeds.arstechnica-{test_id}.com/index",
            crawl_mode="rss",
            is_active=True
        )
        session.add(source)
        await session.flush()

        # 2. Add an Article
        article = Article(
            source_id=source.id,
            url=f"https://arstechnica-{test_id}.com/gadgets/2026/11/color-eink-review",
            title="The Future of Color E-Ink and Mobile Reading",
            author="Technology Editor",
            clean_html="<p>Color E-ink displays have matured rapidly with Kaleido 3 and Gallery 3 panels providing vibrant illustrations for books and magazines.</p>",
            plain_text="Color E-ink displays have matured rapidly with Kaleido 3 and Gallery 3 panels providing vibrant illustrations for books and magazines.",
            excerpt="Color E-ink displays have matured rapidly...",
            word_count=180,
            content_hash=uuid.uuid4().hex[:16],
            relevance_score=8.5,
            is_bundled=False
        )
        session.add(article)
        await session.commit()
        article_id = article.id

    # 3. Trigger compilation
    edition = await compile_daily_edition(limit=5)
    assert edition is not None
    assert edition.article_count >= 1
    assert "AetherPub Daily" in edition.title
    assert Path(edition.file_path).exists()
    assert edition.file_size_bytes > 0

    # In a fresh session, verify article is now marked bundled
    async with AsyncSessionLocal() as verify_session:
        refreshed_art = await verify_session.execute(select(Article).where(Article.id == article_id))
        art_record = refreshed_art.scalar_one()
        assert art_record.is_bundled is True

        # Clean up test records
        await verify_session.delete(art_record)
        refreshed_source = await verify_session.execute(select(Source).where(Source.id == source.id))
        s_rec = refreshed_source.scalar_one_or_none()
        if s_rec:
            await verify_session.delete(s_rec)
        refreshed_ed = await verify_session.execute(select(DailyEdition).where(DailyEdition.id == edition.id))
        e_rec = refreshed_ed.scalar_one_or_none()
        if e_rec:
            await verify_session.delete(e_rec)
        await verify_session.commit()
