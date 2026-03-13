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

    async def close_record(self, record_id: int, closed_at: Optional[datetime] = None) -> Optional[TemporalRecord]:
        """Set valid_to on a record to 'close' it."""
        record = await self.get_by_id(record_id)
        if not record:
            return None
        record.valid_to = closed_at or datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(record)
        return record
