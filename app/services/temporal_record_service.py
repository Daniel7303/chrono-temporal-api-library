from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.temporal_record import TemporalRecord
from app.schemas.temporal_record import TemporalRecordCreate, TemporalRecordUpdate


class TemporalRecordService:

    @staticmethod
    async def create(db: AsyncSession, payload: TemporalRecordCreate) -> TemporalRecord:
        record = TemporalRecord(
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            data=payload.data,
            metadata_=payload.metadata_,
            notes=payload.notes,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record

    @staticmethod
    async def get_by_id(db: AsyncSession, record_id: int) -> Optional[TemporalRecord]:
        result = await db.execute(
            select(TemporalRecord).where(TemporalRecord.id == record_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_history(
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TemporalRecord]:
        """Return all versions of an entity ordered by valid_from."""
        result = await db.execute(
            select(TemporalRecord)
            .where(
                and_(
                    TemporalRecord.entity_type == entity_type,
                    TemporalRecord.entity_id == entity_id,
                )
            )
            .order_by(TemporalRecord.valid_from)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    @staticmethod
    async def get_as_of(
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        as_of: datetime,
    ) -> Optional[TemporalRecord]:
        """Point-in-time query: return the version valid at `as_of`."""
        result = await db.execute(
            select(TemporalRecord)
            .where(
                and_(
                    TemporalRecord.entity_type == entity_type,
                    TemporalRecord.entity_id == entity_id,
                    TemporalRecord.valid_from <= as_of,
                    or_(
                        TemporalRecord.valid_to.is_(None),
                        TemporalRecord.valid_to > as_of,
                    ),
                )
            )
            .order_by(TemporalRecord.valid_from.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_current(
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
    ) -> Optional[TemporalRecord]:
        """Return the currently valid version (valid_to IS NULL)."""
        now = datetime.now(timezone.utc)
        return await TemporalRecordService.get_as_of(db, entity_type, entity_id, now)

    @staticmethod
    async def update(
        db: AsyncSession,
        record_id: int,
        payload: TemporalRecordUpdate,
    ) -> Optional[TemporalRecord]:
        record = await TemporalRecordService.get_by_id(db, record_id)
        if not record:
            return None
        update_data = payload.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            setattr(record, field, value)
        await db.flush()
        await db.refresh(record)
        return record

    @staticmethod
    async def delete(db: AsyncSession, record_id: int) -> bool:
        record = await TemporalRecordService.get_by_id(db, record_id)
        if not record:
            return False
        await db.delete(record)
        return True
