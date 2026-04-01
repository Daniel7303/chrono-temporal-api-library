"""
REST API tests for chrono-temporal FastAPI endpoints.

Tests cover:
- Health endpoint
- Authentication endpoints (generate, list, revoke keys)
- Core temporal endpoints (create, get, history, as-of, diff, close)

Uses an in-memory SQLite database — no PostgreSQL needed.
Run with: pytest tests/test_api.py -v
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Boolean, func

# ── In-memory test database ───────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class TemporalRecord(Base):
    __tablename__ = "temporal_records"
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    data = Column(JSON, nullable=False)
    notes = Column(Text, nullable=True)


class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    hashed_key = Column(String(255), nullable=False, unique=True)
    prefix = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_app():
    """Create a test FastAPI app with in-memory database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    from app.main import app
    from app.db import get_db

    async def override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield app

    app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_app):
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def api_key(client):
    """Generate a real API key for use in protected endpoint tests."""
    resp = await client.post("/auth/keys/", json={"name": "test-key"})
    assert resp.status_code == 201
    return resp.json()["raw_key"]


@pytest_asyncio.fixture(scope="function")
async def auth_headers(api_key):
    """Return headers with a valid API key."""
    return {"X-API-Key": api_key}


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint should return 200 with status ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Authentication ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_api_key(client):
    """Generating an API key should return 201 with a raw_key."""
    resp = await client.post("/auth/keys/", json={"name": "my-app"})
    assert resp.status_code == 201
    body = resp.json()
    assert "raw_key" in body
    assert body["raw_key"].startswith("chron_sk_")
    assert body["name"] == "my-app"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_generated_key_shown_only_once(client):
    """raw_key should only appear in the creation response."""
    await client.post("/auth/keys/", json={"name": "once-only"})
    resp = await client.get("/auth/keys/")
    assert resp.status_code == 200
    for key in resp.json():
        assert "raw_key" not in key


@pytest.mark.asyncio
async def test_list_api_keys(client):
    """List endpoint should return all generated keys."""
    await client.post("/auth/keys/", json={"name": "key-one"})
    await client.post("/auth/keys/", json={"name": "key-two"})
    resp = await client.get("/auth/keys/")
    assert resp.status_code == 200
    names = [k["name"] for k in resp.json()]
    assert "key-one" in names
    assert "key-two" in names


@pytest.mark.asyncio
async def test_revoke_api_key(client):
    """Revoking a key should return 204 and key becomes inactive."""
    create_resp = await client.post("/auth/keys/", json={"name": "to-revoke"})
    key_id = create_resp.json()["id"]
    revoke_resp = await client.delete(f"/auth/keys/{key_id}")
    assert revoke_resp.status_code == 204
    list_resp = await client.get("/auth/keys/")
    revoked = next(k for k in list_resp.json() if k["id"] == key_id)
    assert revoked["is_active"] is False


@pytest.mark.asyncio
async def test_revoke_nonexistent_key(client):
    """Revoking a non-existent key should return 404."""
    resp = await client.delete("/auth/keys/99999")
    assert resp.status_code == 404


# ── Auth protection ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_protected_endpoint_without_key(client):
    """Protected endpoints should return 401 without API key."""
    resp = await client.get("/api/v1/temporal/entity/user/user_001/current")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_invalid_key(client):
    """Protected endpoints should return 401 with an invalid API key."""
    resp = await client.get(
        "/api/v1/temporal/entity/user/user_001/current",
        headers={"X-API-Key": "chron_sk_invalid"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_key(client, auth_headers):
    """Protected endpoints should return 200 with a valid API key."""
    resp = await client.get(
        "/api/v1/temporal/entity/user/user_001/current",
        headers=auth_headers
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_revoked_key_is_rejected(client):
    """A revoked API key should return 401."""
    create_resp = await client.post("/auth/keys/", json={"name": "revoke-me"})
    raw_key = create_resp.json()["raw_key"]
    key_id = create_resp.json()["id"]
    await client.delete(f"/auth/keys/{key_id}")
    resp = await client.get(
        "/api/v1/temporal/entity/user/user_001/current",
        headers={"X-API-Key": raw_key}
    )
    assert resp.status_code == 401


# ── Core temporal endpoints ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_temporal_record(client, auth_headers):
    """POST /api/v1/temporal/ should create and return a record."""
    resp = await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "user",
            "entity_id": "user_001",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
            "data": {"name": "Daniel", "plan": "free"},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["entity_type"] == "user"
    assert body["entity_id"] == "user_001"
    assert body["data"]["plan"] == "free"
    assert body["id"] is not None


@pytest.mark.asyncio
async def test_create_duplicate_active_record_returns_409(client, auth_headers):
    """Creating a second active record for the same entity should return 409."""
    payload = {
        "entity_type": "user",
        "entity_id": "user_dup",
        "valid_from": "2024-01-01T00:00:00Z",
        "valid_to": None,
        "data": {"plan": "free"},
    }
    await client.post("/api/v1/temporal/", json=payload, headers=auth_headers)
    resp = await client.post("/api/v1/temporal/", json=payload, headers=auth_headers)
    assert resp.status_code == 409
    assert "active record already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_record_by_id(client, auth_headers):
    """GET /api/v1/temporal/{id} should return the correct record."""
    create_resp = await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "user",
            "entity_id": "user_002",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
            "data": {"plan": "pro"},
        },
        headers=auth_headers,
    )
    record_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/temporal/{record_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == record_id


@pytest.mark.asyncio
async def test_get_nonexistent_record_returns_404(client, auth_headers):
    """GET /api/v1/temporal/99999 should return 404."""
    resp = await client.get("/api/v1/temporal/99999", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_current(client, auth_headers):
    """GET /current should return the active record."""
    await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "product",
            "entity_id": "prod_001",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
            "data": {"price": 999},
        },
        headers=auth_headers,
    )
    resp = await client.get(
        "/api/v1/temporal/entity/product/prod_001/current",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["data"]["price"] == 999


@pytest.mark.asyncio
async def test_get_history(client, auth_headers):
    """GET /history should return all versions in order."""
    create_resp = await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "product",
            "entity_id": "prod_hist",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
            "data": {"price": 999},
        },
        headers=auth_headers,
    )
    record_id = create_resp.json()["id"]
    await client.patch(
        f"/api/v1/temporal/{record_id}/close",
        params={"closed_at": "2024-06-01T00:00:00Z"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "product",
            "entity_id": "prod_hist",
            "valid_from": "2024-06-01T00:00:00Z",
            "valid_to": None,
            "data": {"price": 599},
        },
        headers=auth_headers,
    )
    resp = await client.get(
        "/api/v1/temporal/entity/product/prod_hist/history",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.json()[0]["data"]["price"] == 999
    assert resp.json()[1]["data"]["price"] == 599


@pytest.mark.asyncio
async def test_get_as_of(client, auth_headers):
    """GET /as-of should return the correct version for a given date."""
    create_resp = await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "product",
            "entity_id": "prod_asof",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
            "data": {"price": 999},
        },
        headers=auth_headers,
    )
    record_id = create_resp.json()["id"]
    await client.patch(
        f"/api/v1/temporal/{record_id}/close",
        params={"closed_at": "2024-06-01T00:00:00Z"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "product",
            "entity_id": "prod_asof",
            "valid_from": "2024-06-01T00:00:00Z",
            "valid_to": None,
            "data": {"price": 599},
        },
        headers=auth_headers,
    )

    # Before price drop
    resp = await client.get(
        "/api/v1/temporal/entity/product/prod_asof/as-of",
        params={"as_of": "2024-03-01T00:00:00Z"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["data"]["price"] == 999

    # After price drop
    resp = await client.get(
        "/api/v1/temporal/entity/product/prod_asof/as-of",
        params={"as_of": "2024-07-01T00:00:00Z"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["data"]["price"] == 599


@pytest.mark.asyncio
async def test_get_diff(client, auth_headers):
    """GET /diff should return correct changed, added, removed fields."""
    create_resp = await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "user",
            "entity_id": "user_diff",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
            "data": {"name": "Daniel", "plan": "free", "email": "d@example.com"},
        },
        headers=auth_headers,
    )
    record_id = create_resp.json()["id"]
    await client.patch(
        f"/api/v1/temporal/{record_id}/close",
        params={"closed_at": "2024-06-01T00:00:00Z"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "user",
            "entity_id": "user_diff",
            "valid_from": "2024-06-01T00:00:00Z",
            "valid_to": None,
            "data": {"name": "Daniel", "plan": "pro", "email": "d@example.com"},
        },
        headers=auth_headers,
    )
    resp = await client.get(
        "/api/v1/temporal/entity/user/user_diff/diff",
        params={
            "from_dt": "2024-03-01T00:00:00Z",
            "to_dt": "2024-07-01T00:00:00Z",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_changes"] is True
    assert "plan" in body["changed"]
    assert body["changed"]["plan"]["from"] == "free"
    assert body["changed"]["plan"]["to"] == "pro"
    assert "name" in body["unchanged"]
    assert "email" in body["unchanged"]


@pytest.mark.asyncio
async def test_close_record(client, auth_headers):
    """PATCH /close should set valid_to on the record."""
    create_resp = await client.post(
        "/api/v1/temporal/",
        json={
            "entity_type": "user",
            "entity_id": "user_close",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_to": None,
            "data": {"plan": "free"},
        },
        headers=auth_headers,
    )
    record_id = create_resp.json()["id"]
    assert create_resp.json()["valid_to"] is None

    resp = await client.patch(
        f"/api/v1/temporal/{record_id}/close",
        params={"closed_at": "2024-06-01T00:00:00Z"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["valid_to"] is not None


@pytest.mark.asyncio
async def test_close_nonexistent_record_returns_404(client, auth_headers):
    """PATCH /close on non-existent record should return 404."""
    resp = await client.patch(
        "/api/v1/temporal/99999/close",
        headers=auth_headers,
    )
    assert resp.status_code == 404
