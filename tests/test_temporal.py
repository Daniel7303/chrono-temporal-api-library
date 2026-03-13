import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_record():
    payload = {
        "entity_type": "employee",
        "entity_id": "emp-001",
        "valid_from": "2024-01-01T00:00:00Z",
        "valid_to": None,
        "data": {"name": "Alice", "department": "Engineering"},
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/temporal/", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["entity_id"] == "emp-001"
    assert body["id"] is not None
