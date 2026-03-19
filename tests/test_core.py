"""
Tests for chrono-temporal core library.

Uses an in-memory SQLite database so no PostgreSQL is needed to run tests.
Run with: pytest tests/test_core.py -v
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, func

# ── In-memory test database setup ─────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class TemporalRecord(Base):
    """Mirror of the real model — used for in-memory testing."""
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


# Use aiosqlite for in-memory async testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────────

def dt(year, month, day):
    """Shorthand for creating timezone-aware datetimes."""
    return datetime(year, month, day, tzinfo=timezone.utc)


async def create_record(session, entity_type, entity_id, valid_from, data, valid_to=None, notes=None):
    """Helper to insert a temporal record directly."""
    record = TemporalRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        valid_from=valid_from,
        valid_to=valid_to,
        data=data,
        notes=notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


# ── Import service (with path adjustment for in-memory model) ─────────────────
# We test the logic directly since we're using an in-memory model
from sqlalchemy import select, and_, or_


class TemporalService:
    """
    Inline service for testing — mirrors the real TemporalService
    but operates on the in-memory TemporalRecord model.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_current(self, entity_type, entity_id):
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(TemporalRecord).where(
                and_(
                    TemporalRecord.entity_type == entity_type,
                    TemporalRecord.entity_id == entity_id,
                    TemporalRecord.valid_from <= now,
                    or_(
                        TemporalRecord.valid_to.is_(None),
                        TemporalRecord.valid_to > now,
                    ),
                )
            ).order_by(TemporalRecord.valid_from.desc())
        )
        return result.scalars().all()

    async def get_at_point_in_time(self, entity_type, entity_id, as_of):
        result = await self.db.execute(
            select(TemporalRecord).where(
                and_(
                    TemporalRecord.entity_type == entity_type,
                    TemporalRecord.entity_id == entity_id,
                    TemporalRecord.valid_from <= as_of,
                    or_(
                        TemporalRecord.valid_to.is_(None),
                        TemporalRecord.valid_to > as_of,
                    ),
                )
            ).order_by(TemporalRecord.valid_from.desc())
        )
        return result.scalars().all()

    async def get_history(self, entity_type, entity_id):
        result = await self.db.execute(
            select(TemporalRecord).where(
                and_(
                    TemporalRecord.entity_type == entity_type,
                    TemporalRecord.entity_id == entity_id,
                )
            ).order_by(TemporalRecord.valid_from.asc())
        )
        return result.scalars().all()

    async def close_record(self, record_id, closed_at=None):
        result = await self.db.execute(
            select(TemporalRecord).where(TemporalRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        record.valid_to = closed_at or datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_diff(self, entity_type, entity_id, from_dt, to_dt):
        async def get_snapshot(at):
            result = await self.db.execute(
                select(TemporalRecord).where(
                    and_(
                        TemporalRecord.entity_type == entity_type,
                        TemporalRecord.entity_id == entity_id,
                        TemporalRecord.valid_from <= at,
                        or_(
                            TemporalRecord.valid_to.is_(None),
                            TemporalRecord.valid_to > at,
                        ),
                    )
                ).order_by(TemporalRecord.valid_from.desc())
            )
            records = result.scalars().all()
            return records[0].data if records else None

        from_data = await get_snapshot(from_dt)
        to_data = await get_snapshot(to_dt)

        if from_data is None and to_data is None:
            return {"error": "No records found at either point in time"}
        if from_data is None:
            return {"error": f"No records found at {from_dt}", "to": to_data}
        if to_data is None:
            return {"error": f"No records found at {to_dt}", "from": from_data}

        all_keys = set(from_data.keys()) | set(to_data.keys())
        changed, unchanged, added, removed = {}, [], {}, {}

        for key in all_keys:
            if key not in from_data:
                added[key] = to_data[key]
            elif key not in to_data:
                removed[key] = from_data[key]
            elif from_data[key] != to_data[key]:
                changed[key] = {"from": from_data[key], "to": to_data[key]}
            else:
                unchanged.append(key)

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "from": str(from_dt),
            "to": str(to_dt),
            "changed": changed,
            "added": added,
            "removed": removed,
            "unchanged": unchanged,
            "has_changes": bool(changed or added or removed),
        }

    async def has_active_record(self, entity_type, entity_id):
        """Check if an entity already has an active (open) record."""
        result = await self.db.execute(
            select(TemporalRecord).where(
                and_(
                    TemporalRecord.entity_type == entity_type,
                    TemporalRecord.entity_id == entity_id,
                    TemporalRecord.valid_to.is_(None),
                )
            )
        )
        return result.scalar_one_or_none() is not None


# ── Tests: create ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_record_persists(db_session):
    """Creating a record should persist it with correct fields."""
    record = await create_record(
        db_session, "user", "user_001",
        valid_from=dt(2024, 1, 1),
        data={"name": "Daniel", "plan": "free"},
        notes="Initial record",
    )

    assert record.id is not None
    assert record.entity_type == "user"
    assert record.entity_id == "user_001"
    assert record.data["plan"] == "free"
    assert record.valid_to is None
    assert record.notes == "Initial record"


@pytest.mark.asyncio
async def test_create_multiple_records_for_same_entity(db_session):
    """Multiple records can exist for the same entity (different time periods)."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"plan": "free"}, valid_to=dt(2025, 1, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 1, 1),
                        {"plan": "pro"})

    svc = TemporalService(db_session)
    history = await svc.get_history("user", "user_001")
    assert len(history) == 2


# ── Tests: get_current ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_current_returns_active_record(db_session):
    """get_current should return the record with valid_to=None."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"plan": "free"}, valid_to=dt(2025, 1, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 1, 1),
                        {"plan": "pro"})

    svc = TemporalService(db_session)
    current = await svc.get_current("user", "user_001")

    assert len(current) == 1
    assert current[0].data["plan"] == "pro"


@pytest.mark.asyncio
async def test_get_current_returns_empty_when_all_closed(db_session):
    """get_current should return empty list when all records are closed."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"plan": "free"}, valid_to=dt(2024, 6, 1))

    svc = TemporalService(db_session)
    current = await svc.get_current("user", "user_001")
    assert current == []


@pytest.mark.asyncio
async def test_get_current_ignores_other_entities(db_session):
    """get_current should only return records for the requested entity."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1), {"plan": "free"})
    await create_record(db_session, "user", "user_002", dt(2024, 1, 1), {"plan": "pro"})

    svc = TemporalService(db_session)
    current = await svc.get_current("user", "user_001")

    assert len(current) == 1
    assert current[0].data["plan"] == "free"


# ── Tests: get_at_point_in_time ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_time_travel_returns_correct_version(db_session):
    """Time-travel query should return the correct version for a given date."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"plan": "free"}, valid_to=dt(2025, 6, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 6, 1),
                        {"plan": "pro"})

    svc = TemporalService(db_session)

    # Query before upgrade — should return free
    before = await svc.get_at_point_in_time("user", "user_001", dt(2024, 6, 1))
    assert len(before) == 1
    assert before[0].data["plan"] == "free"

    # Query after upgrade — should return pro
    after = await svc.get_at_point_in_time("user", "user_001", dt(2025, 7, 1))
    assert len(after) == 1
    assert after[0].data["plan"] == "pro"


@pytest.mark.asyncio
async def test_time_travel_returns_empty_before_first_record(db_session):
    """Time-travel query before the first record should return empty."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1), {"plan": "free"})

    svc = TemporalService(db_session)
    result = await svc.get_at_point_in_time("user", "user_001", dt(2023, 1, 1))
    assert result == []


@pytest.mark.asyncio
async def test_time_travel_at_exact_boundary(db_session):
    """Time-travel at exact valid_from boundary should return the new record."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"plan": "free"}, valid_to=dt(2025, 6, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 6, 1),
                        {"plan": "pro"})

    svc = TemporalService(db_session)
    result = await svc.get_at_point_in_time("user", "user_001", dt(2025, 6, 1))
    assert result[0].data["plan"] == "pro"


# ── Tests: get_history ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_history_returns_all_versions_in_order(db_session):
    """get_history should return all records ordered by valid_from ascending."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"plan": "free"}, valid_to=dt(2025, 1, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 1, 1),
                        {"plan": "pro"}, valid_to=dt(2025, 6, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 6, 1),
                        {"plan": "enterprise"})

    svc = TemporalService(db_session)
    history = await svc.get_history("user", "user_001")

    assert len(history) == 3
    assert history[0].data["plan"] == "free"
    assert history[1].data["plan"] == "pro"
    assert history[2].data["plan"] == "enterprise"


@pytest.mark.asyncio
async def test_get_history_returns_empty_for_unknown_entity(db_session):
    """get_history should return empty list for an entity that doesn't exist."""
    svc = TemporalService(db_session)
    history = await svc.get_history("user", "nonexistent")
    assert history == []


# ── Tests: close_record ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close_record_sets_valid_to(db_session):
    """close_record should set valid_to on the specified record."""
    record = await create_record(db_session, "user", "user_001",
                                 dt(2024, 1, 1), {"plan": "free"})
    assert record.valid_to is None

    svc = TemporalService(db_session)
    closed = await svc.close_record(record.id, closed_at=dt(2025, 6, 1))

    assert closed.valid_to is not None
    assert closed.valid_to.year == 2025
    assert closed.valid_to.month == 6


@pytest.mark.asyncio
async def test_close_record_returns_none_for_missing_id(db_session):
    """close_record should return None for a non-existent record ID."""
    svc = TemporalService(db_session)
    result = await svc.close_record(99999)
    assert result is None


@pytest.mark.asyncio
async def test_closed_record_not_returned_as_current(db_session):
    """After closing a record, get_current should not return it."""
    record = await create_record(db_session, "user", "user_001",
                                 dt(2024, 1, 1), {"plan": "free"})

    svc = TemporalService(db_session)
    await svc.close_record(record.id, closed_at=dt(2024, 6, 1))

    current = await svc.get_current("user", "user_001")
    assert current == []


# ── Tests: get_diff ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_diff_detects_changed_fields(db_session):
    """get_diff should correctly identify changed fields."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"name": "Daniel", "plan": "free", "email": "d@example.com"},
                        valid_to=dt(2025, 6, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 6, 1),
                        {"name": "Daniel", "plan": "pro", "email": "d@example.com"})

    svc = TemporalService(db_session)
    diff = await svc.get_diff("user", "user_001", dt(2024, 3, 1), dt(2025, 7, 1))

    assert diff["has_changes"] is True
    assert "plan" in diff["changed"]
    assert diff["changed"]["plan"]["from"] == "free"
    assert diff["changed"]["plan"]["to"] == "pro"
    assert "name" in diff["unchanged"]
    assert "email" in diff["unchanged"]


@pytest.mark.asyncio
async def test_diff_detects_added_fields(db_session):
    """get_diff should detect fields that were added in a new version."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"name": "Daniel", "plan": "free"},
                        valid_to=dt(2025, 1, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 1, 1),
                        {"name": "Daniel", "plan": "free", "phone": "+1234567890"})

    svc = TemporalService(db_session)
    diff = await svc.get_diff("user", "user_001", dt(2024, 6, 1), dt(2025, 6, 1))

    assert "phone" in diff["added"]
    assert diff["added"]["phone"] == "+1234567890"
    assert diff["has_changes"] is True


@pytest.mark.asyncio
async def test_diff_detects_removed_fields(db_session):
    """get_diff should detect fields that were removed in a new version."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"name": "Daniel", "plan": "free", "phone": "+1234567890"},
                        valid_to=dt(2025, 1, 1))
    await create_record(db_session, "user", "user_001", dt(2025, 1, 1),
                        {"name": "Daniel", "plan": "free"})

    svc = TemporalService(db_session)
    diff = await svc.get_diff("user", "user_001", dt(2024, 6, 1), dt(2025, 6, 1))

    assert "phone" in diff["removed"]
    assert diff["has_changes"] is True


@pytest.mark.asyncio
async def test_diff_no_changes(db_session):
    """get_diff should return has_changes=False when nothing changed."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"name": "Daniel", "plan": "free"})

    svc = TemporalService(db_session)
    diff = await svc.get_diff("user", "user_001", dt(2024, 3, 1), dt(2024, 6, 1))

    assert diff["has_changes"] is False
    assert diff["changed"] == {}


@pytest.mark.asyncio
async def test_diff_returns_error_for_missing_entity(db_session):
    """get_diff should return an error dict when entity doesn't exist."""
    svc = TemporalService(db_session)
    diff = await svc.get_diff("user", "nonexistent", dt(2024, 1, 1), dt(2025, 1, 1))

    assert "error" in diff


# ── Tests: overlap protection ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_has_active_record_returns_true_when_open_record_exists(db_session):
    """has_active_record should return True when an open record exists."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1), {"plan": "free"})

    svc = TemporalService(db_session)
    assert await svc.has_active_record("user", "user_001") is True


@pytest.mark.asyncio
async def test_has_active_record_returns_false_when_all_closed(db_session):
    """has_active_record should return False when all records are closed."""
    await create_record(db_session, "user", "user_001", dt(2024, 1, 1),
                        {"plan": "free"}, valid_to=dt(2025, 1, 1))

    svc = TemporalService(db_session)
    assert await svc.has_active_record("user", "user_001") is False


@pytest.mark.asyncio
async def test_has_active_record_returns_false_for_unknown_entity(db_session):
    """has_active_record should return False for an entity with no records."""
    svc = TemporalService(db_session)
    assert await svc.has_active_record("user", "nonexistent") is False


# ── Tests: isolation between entity types ─────────────────────────────────────

@pytest.mark.asyncio
async def test_different_entity_types_are_isolated(db_session):
    """Records for different entity types should not interfere."""
    await create_record(db_session, "user", "001", dt(2024, 1, 1), {"plan": "free"})
    await create_record(db_session, "product", "001", dt(2024, 1, 1), {"price": 99.99})

    svc = TemporalService(db_session)

    user_history = await svc.get_history("user", "001")
    product_history = await svc.get_history("product", "001")

    assert len(user_history) == 1
    assert len(product_history) == 1
    assert user_history[0].data["plan"] == "free"
    assert product_history[0].data["price"] == 99.99
