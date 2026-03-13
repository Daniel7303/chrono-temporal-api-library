from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Optional


class TemporalRecordBase(BaseModel):
    entity_type: str = Field(..., max_length=100, description="Type of entity, e.g. 'employee', 'product'")
    entity_id: str = Field(..., max_length=255, description="Unique ID of the entity")
    valid_from: datetime = Field(..., description="When this record became valid in reality")
    valid_to: Optional[datetime] = Field(None, description="When this record stopped being valid (null = current)")
    data: dict[str, Any] = Field(..., description="The payload for this version")
    notes: Optional[str] = None


class TemporalRecordCreate(TemporalRecordBase):
    pass


class TemporalRecordUpdate(BaseModel):
    valid_to: Optional[datetime] = None
    data: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class TemporalRecordRead(TemporalRecordBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}
