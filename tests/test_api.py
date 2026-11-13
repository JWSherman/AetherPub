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
