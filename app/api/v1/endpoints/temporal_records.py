from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.temporal_record import (
    TemporalRecordCreate,
    TemporalRecordUpdate,
    TemporalRecordResponse,
)
from app.services.temporal_record_service import TemporalRecordService

router = APIRouter(prefix="/records", tags=["Temporal Records"])


@router.post("/", response_model=TemporalRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_record(payload: TemporalRecordCreate, db: AsyncSession = Depends(get_db)):
    """Create a new temporal record (a versioned snapshot of an entity)."""
    return await TemporalRecordService.create(db, payload)


@router.get("/{record_id}", response_model=TemporalRecordResponse)
async def get_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch a specific temporal record by its internal ID."""
    record = await TemporalRecordService.get_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("/{entity_type}/{entity_id}/history", response_model=list[TemporalRecordResponse])
async def get_history(
    entity_type: str,
    entity_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return all versions of an entity ordered chronologically."""
    return await TemporalRecordService.get_history(db, entity_type, entity_id, limit, offset)


@router.get("/{entity_type}/{entity_id}/as-of", response_model=TemporalRecordResponse)
async def get_as_of(
    entity_type: str,
    entity_id: str,
    as_of: datetime = Query(..., description="ISO-8601 datetime for point-in-time query"),
    db: AsyncSession = Depends(get_db),
):
    """Point-in-time query: return the version valid at the given datetime."""
    record = await TemporalRecordService.get_as_of(db, entity_type, entity_id, as_of)
    if not record:
        raise HTTPException(status_code=404, detail=f"No record valid at {as_of}")
    return record


@router.get("/{entity_type}/{entity_id}/current", response_model=TemporalRecordResponse)
async def get_current(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return the currently valid version of an entity."""
    record = await TemporalRecordService.get_current(db, entity_type, entity_id)
    if not record:
        raise HTTPException(status_code=404, detail="No current record found")
    return record


@router.patch("/{record_id}", response_model=TemporalRecordResponse)
async def update_record(
    record_id: int,
    payload: TemporalRecordUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update mutable fields on a temporal record (e.g. close it by setting valid_to)."""
    record = await TemporalRecordService.update(db, record_id, payload)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """Hard-delete a temporal record (use with caution — prefer closing with valid_to)."""
    deleted = await TemporalRecordService.delete(db, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
