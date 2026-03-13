from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime, timezone
from typing import Optional
from app.models.temporal_record import TemporalRecord
from app.schemas.temporal_record import TemporalRecordCreate, TemporalRecordUpdate


class TemporalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: TemporalRecordCreate) -> TemporalRecord:
        record = TemporalRecord(**payload.model_dump())
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_by_id(self, record_id: int) -> Optional[TemporalRecord]:
        result = await self.db.execute(
            select(TemporalRecord).where(TemporalRecord.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_current(self, entity_type: str, entity_id: str) -> list[TemporalRecord]:
        """Get records valid right now (valid_to is NULL or in the future)."""
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

    async def get_at_point_in_time(
        self, entity_type: str, entity_id: str, as_of: datetime
    ) -> list[TemporalRecord]:
        """Get records valid at a specific point in time."""
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

    async def get_history(self, entity_type: str, entity_id: str) -> list[TemporalRecord]:
        """Get full timeline of an entity."""
        result = await self.db.execute(
            select(TemporalRecord).where(
                and_(
                    TemporalRecord.entity_type == entity_type,
                    TemporalRecord.entity_id == entity_id,
                )
            ).order_by(TemporalRecord.valid_from.asc())
        )
        return result.scalars().all()

    async def get_diff(
        self, entity_type: str, entity_id: str, from_dt: datetime, to_dt: datetime
    ) -> dict:
        """Compare entity state between two points in time and return what changed."""

        async def get_snapshot(at: datetime):
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
            return {"error": "No records found for this entity at either point in time"}

        if from_data is None:
            return {"error": f"No records found at {from_dt}", "to": to_data}

        if to_data is None:
            return {"error": f"No records found at {to_dt}", "from": from_data}

        # Compute the diff
        all_keys = set(from_data.keys()) | set(to_data.keys())
        changed = {}
        unchanged = []
        added = {}
        removed = {}

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

    async def close_record(self, record_id: int, closed_at: Optional[datetime] = None) -> Optional[TemporalRecord]:
        """Set valid_to on a record to 'close' it."""
        record = await self.get_by_id(record_id)
        if not record:
            return None
        record.valid_to = closed_at or datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(record)
        return record
