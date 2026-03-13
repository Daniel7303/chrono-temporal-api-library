from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
from app.db import get_db
from app.schemas import TemporalRecordCreate, TemporalRecordRead
from app.services import TemporalService

router = APIRouter(prefix="/temporal", tags=["Temporal Records"])


@router.post("/", response_model=TemporalRecordRead, status_code=201)
async def create_record(payload: TemporalRecordCreate, db: AsyncSession = Depends(get_db)):
    """Create a new temporal record."""
    svc = TemporalService(db)
    return await svc.create(payload)


@router.get("/{record_id}", response_model=TemporalRecordRead)
async def get_record(record_id: int, db: AsyncSession = Depends(get_db)):
    svc = TemporalService(db)
    record = await svc.get_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("/entity/{entity_type}/{entity_id}/current", response_model=list[TemporalRecordRead])
async def get_current(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    """Get currently valid records for an entity."""
    svc = TemporalService(db)
    return await svc.get_current(entity_type, entity_id)


@router.get("/entity/{entity_type}/{entity_id}/history", response_model=list[TemporalRecordRead])
async def get_history(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    """Get full history for an entity."""
    svc = TemporalService(db)
    return await svc.get_history(entity_type, entity_id)


@router.get("/entity/{entity_type}/{entity_id}/as-of", response_model=list[TemporalRecordRead])
async def get_as_of(
    entity_type: str,
    entity_id: str,
    as_of: datetime = Query(..., description="ISO 8601 datetime, e.g. 2024-01-15T00:00:00Z"),
    db: AsyncSession = Depends(get_db),
):
    """Get records valid at a specific point in time."""
    svc = TemporalService(db)
    return await svc.get_at_point_in_time(entity_type, entity_id, as_of)


@router.patch("/{record_id}/close", response_model=TemporalRecordRead)
async def close_record(
    record_id: int,
    closed_at: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Close a record (set valid_to)."""
    svc = TemporalService(db)
    record = await svc.close_record(record_id, closed_at)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
