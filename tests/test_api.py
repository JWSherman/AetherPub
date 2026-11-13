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
