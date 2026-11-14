import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import init_db

@pytest.mark.asyncio
async def test_api_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "AetherPub"

@pytest.mark.asyncio
async def test_keyword_crud_and_evaluate():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create Keyword
        create_resp = await ac.post("/api/v1/keywords", json={
            "term": "robotics",
            "weight": 2.5,
            "is_required": False,
            "is_excluded": False
        })
        assert create_resp.status_code == 200
        kw = create_resp.json()
        assert kw["term"] == "robotics"
        assert kw["weight"] == 2.5
        kw_id = kw["id"]

        # List Keywords
        list_resp = await ac.get("/api/v1/keywords")
        assert list_resp.status_code == 200
        terms = [k["term"] for k in list_resp.json()]
        assert "robotics" in terms

        # Update Keyword Weight (PATCH)
        patch_resp = await ac.patch(f"/api/v1/keywords/{kw_id}", json={
            "weight": 4.0
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["weight"] == 4.0

        # Evaluate Sandbox
        eval_resp = await ac.post("/api/v1/keywords/evaluate", json={
            "title": "Robotics in Space Exploration",
            "content": "Autonomous robotics agents are being deployed to navigate extraterrestrial terrain."
        })
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["score"] > 0
        assert eval_data["is_excluded_match"] is False

        # Delete Keyword
        del_resp = await ac.delete(f"/api/v1/keywords/{kw_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

@pytest.mark.asyncio
async def test_direct_feed_probe_and_multiple_feeds_same_domain():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Mock probe with a mock RSS XML URL
        sample_rss_url = "https://gameinformer.com/reviews.xml"
        probe_resp = await ac.post("/api/v1/sources/probe", json={"url": sample_rss_url})
        assert probe_resp.status_code == 200
        data = probe_resp.json()
        assert data["crawl_mode"] == "rss"
        assert "gameinformer.com/reviews.xml" in data["feed_url"]
        assert len(data["preview"]) > 0

        # Add Source 1 (Reviews feed)
        add_resp1 = await ac.post("/api/v1/sources", json={
            "url": sample_rss_url,
            "name": "Game Informer Reviews",
            "feed_url": sample_rss_url
        })
        assert add_resp1.status_code == 200
        src1 = add_resp1.json()
        assert src1["name"] == "Game Informer Reviews"
        assert src1["feed_url"] == sample_rss_url

        # Add Source 2 from same domain (News feed)
        sample_news_url = "https://gameinformer.com/news.xml"
        add_resp2 = await ac.post("/api/v1/sources", json={
            "url": sample_news_url,
            "name": "Game Informer News",
            "feed_url": sample_news_url
        })
        # Should NOT fail with 409 because the feed_url is distinct
        assert add_resp2.status_code == 200
        src2 = add_resp2.json()
        assert src2["name"] == "Game Informer News"

        # Cleanup
        await ac.delete(f"/api/v1/sources/{src1['id']}")
        await ac.delete(f"/api/v1/sources/{src2['id']}")

@pytest.mark.asyncio
async def test_curation_curves_and_source_weight_api():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Get Curves
        curves_resp = await ac.get("/api/v1/curation/curves")
        assert curves_resp.status_code == 200
        curves = curves_resp.json()
        assert "age_curve" in curves
        assert "length_curve" in curves
        assert len(curves["age_curve"]) > 0

        # 2. Update Curves
        new_age = [{"x": 0.0, "y": 6.0}, {"x": 5.0, "y": 2.0}, {"x": 30.0, "y": -5.0}]
        new_len = [{"x": 0.0, "y": -2.0}, {"x": 1000.0, "y": 4.0}]
        put_resp = await ac.put("/api/v1/curation/curves", json={
            "age_curve": new_age,
            "length_curve": new_len
        })
        assert put_resp.status_code == 200
        saved = put_resp.json()
        assert len(saved["age_curve"]) == 3

        # 3. Recalculate scores
        recalc_resp = await ac.post("/api/v1/curation/recalculate-scores")
        assert recalc_resp.status_code == 200
        assert "updated_articles" in recalc_resp.json()

@pytest.mark.asyncio
async def test_editions_download_timestamps_and_delete(tmp_path):
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.models.entities import DailyEdition

    await init_db()

    epub_file = tmp_path / "test_edition.epub"
    epub_file.write_bytes(b"PK\x03\x04dummy-epub-bytes")
    cover_file = tmp_path / "test_edition_cover.jpg"
    cover_file.write_bytes(b"\xff\xd8\xff\xe0dummy-jpeg")

    async with AsyncSessionLocal() as session:
        edition = DailyEdition(
            title="Test File Manager Digest",
            edition_date="2026-11-14",
            article_count=3,
            total_word_count=1500,
            file_path=str(epub_file),
            cover_path=str(cover_file),
            file_size_bytes=24
        )
        session.add(edition)
        await session.commit()
        edition_id = edition.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Initially never downloaded
        list_resp = await ac.get("/api/v1/editions")
        assert list_resp.status_code == 200
        found = next(e for e in list_resp.json() if e["id"] == edition_id)
        assert found["download_count"] == 0
        assert found["last_downloaded_at"] is None
        assert found["download_timestamps"] == []

        # Download twice to record download date-times
        dl1 = await ac.get(f"/api/v1/editions/{edition_id}/download")
        assert dl1.status_code == 200
        dl2 = await ac.get(f"/api/v1/editions/{edition_id}/download")
        assert dl2.status_code == 200

        # Verify download count and date-time history are recorded
        detail_resp = await ac.get(f"/api/v1/editions/{edition_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["download_count"] == 2
        assert detail["last_downloaded_at"] is not None
        assert len(detail["download_timestamps"]) == 2

        # Delete the edition via File Manager delete endpoint
        del_resp = await ac.delete(f"/api/v1/editions/{edition_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Files on disk and DB record should be removed
        assert not epub_file.exists()
        assert not cover_file.exists()
        missing_resp = await ac.get(f"/api/v1/editions/{edition_id}")
        assert missing_resp.status_code == 404

@pytest.mark.asyncio
async def test_reset_bundled_articles():
    import uuid
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.models.entities import Source, Article

    await init_db()

    async with AsyncSessionLocal() as session:
        src = Source(
            name="Test Reset Source",
            base_url=f"https://example.com/{uuid.uuid4().hex[:8]}",
            crawl_mode="rss"
        )
        session.add(src)
        await session.flush()

        art = Article(
            source_id=src.id,
            url=f"https://example.com/post-{uuid.uuid4().hex[:8]}",
            title="Bundled Test Article",
            clean_html="<div class='article-content'><p>Test body</p></div>",
            plain_text="Test body",
            word_count=100,
            content_hash=uuid.uuid4().hex[:16],
            relevance_score=5.0,
            is_bundled=True
        )
        session.add(art)
        await session.commit()
        src_id = src.id
        art_id = art.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        reset_resp = await ac.post("/api/v1/articles/reset-bundled")
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()
        assert reset_data["status"] == "success"
        assert reset_data["reset_count"] >= 1

        art_resp = await ac.get(f"/api/v1/articles/{art_id}")
        assert art_resp.status_code == 200
        assert art_resp.json()["is_bundled"] is False

        # Cleanup
        await ac.delete(f"/api/v1/sources/{src_id}")

@pytest.mark.asyncio
async def test_image_quality_settings_and_epub_recompression():
    import io
    import zipfile
    from PIL import Image
    from backend.app.services.delivery.smtp_client import SMTPDeliveryService

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        get_resp = await ac.get("/api/v1/settings")
        assert get_resp.status_code == 200
        initial = get_resp.json()
        assert "JPEG_QUALITY" in initial
        assert "MAX_IMAGE_WIDTH" in initial

        save_resp = await ac.post("/api/v1/settings", json={
            "JPEG_QUALITY": "40",
            "MAX_IMAGE_WIDTH": "1000"
        })
        assert save_resp.status_code == 200

        updated = (await ac.get("/api/v1/settings")).json()
        assert updated["JPEG_QUALITY"] == "40"
        assert updated["MAX_IMAGE_WIDTH"] == "1000"

        # Restore defaults
        await ac.post("/api/v1/settings", json={
            "JPEG_QUALITY": "85",
            "MAX_IMAGE_WIDTH": "1600"
        })

    # Verify in-memory EPUB image recompression for SMTP
    img = Image.effect_mandelbrot((1600, 1600), (-2.0, -1.5, 1.0, 1.5), 64).convert("RGB")
    img_buf = io.BytesIO()
    img.save(img_buf, format="JPEG", quality=92)
    orig_img_bytes = img_buf.getvalue()

    epub_buf = io.BytesIO()
    with zipfile.ZipFile(epub_buf, "w") as zf:
        zf.writestr("EPUB/images/sample.jpg", orig_img_bytes)
        zf.writestr("EPUB/chapter_1.xhtml", b"<html><body>Test</body></html>")
    orig_epub = epub_buf.getvalue()

    compressed_epub = SMTPDeliveryService._recompress_epub_images(orig_epub, jpeg_quality=35, max_dim=800)
    assert len(compressed_epub) < len(orig_epub)
    with zipfile.ZipFile(io.BytesIO(compressed_epub), "r") as zf:
        re_img = Image.open(io.BytesIO(zf.read("EPUB/images/sample.jpg")))
        assert re_img.mode == "RGB"
        assert max(re_img.size) <= 800

@pytest.mark.asyncio
async def test_articles_sorting_options():
    import uuid
    from datetime import datetime, timezone, timedelta
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.models.entities import Source, Article

    await init_db()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        src = Source(
            name="Test Sorting Source",
            base_url=f"https://example.com/{uuid.uuid4().hex[:8]}",
            crawl_mode="rss"
        )
        session.add(src)
        await session.flush()

        art_alpha = Article(
            source_id=src.id,
            url=f"https://example.com/alpha-{uuid.uuid4().hex[:8]}",
            title="Alpha Article",
            published_at=now - timedelta(days=3),
            clean_html="<div class='article-content'><p>Alpha</p></div>",
            plain_text="Alpha",
            word_count=300,
            content_hash=uuid.uuid4().hex[:16],
            relevance_score=9.5,
            is_bundled=True
        )
        art_zeta = Article(
            source_id=src.id,
            url=f"https://example.com/zeta-{uuid.uuid4().hex[:8]}",
            title="Zeta Article",
            published_at=now - timedelta(days=1),
            clean_html="<div class='article-content'><p>Zeta</p></div>",
            plain_text="Zeta",
            word_count=1800,
            content_hash=uuid.uuid4().hex[:16],
            relevance_score=2.0,
            is_bundled=False
        )
        session.add_all([art_alpha, art_zeta])
        await session.commit()
        src_id = src.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Sort by score descending
        score_desc = (await ac.get(f"/api/v1/articles?source_id={src_id}&sort_by=score_desc")).json()
        assert [a["title"] for a in score_desc] == ["Alpha Article", "Zeta Article"]

        # Sort by score ascending
        score_asc = (await ac.get(f"/api/v1/articles?source_id={src_id}&sort_by=score_asc")).json()
        assert [a["title"] for a in score_asc] == ["Zeta Article", "Alpha Article"]

        # Sort by date descending (newest first)
        date_desc = (await ac.get(f"/api/v1/articles?source_id={src_id}&sort_by=date_desc")).json()
        assert [a["title"] for a in date_desc] == ["Zeta Article", "Alpha Article"]

        # Sort by date ascending (oldest first)
        date_asc = (await ac.get(f"/api/v1/articles?source_id={src_id}&sort_by=date_asc")).json()
        assert [a["title"] for a in date_asc] == ["Alpha Article", "Zeta Article"]

        # Sort by word count descending
        words_desc = (await ac.get(f"/api/v1/articles?source_id={src_id}&sort_by=words_desc")).json()
        assert [a["title"] for a in words_desc] == ["Zeta Article", "Alpha Article"]

        # Sort by title A-Z
        title_asc = (await ac.get(f"/api/v1/articles?source_id={src_id}&sort_by=title_asc")).json()
        assert [a["title"] for a in title_asc] == ["Alpha Article", "Zeta Article"]

        # Sort by status ready first (unbundled first)
        status_ready = (await ac.get(f"/api/v1/articles?source_id={src_id}&sort_by=status_ready")).json()
        assert [a["title"] for a in status_ready] == ["Zeta Article", "Alpha Article"]

        # Cleanup
        await ac.delete(f"/api/v1/sources/{src_id}")
