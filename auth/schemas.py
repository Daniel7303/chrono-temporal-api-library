from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class APIKeyCreate(BaseModel):
    name: str  # a label like "production" or "my-app"


class APIKeyRead(BaseModel):
    id: int
    name: str
    prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class APIKeyCreated(APIKeyRead):
    """Returned only once at creation time — includes the full raw key."""
    raw_key: str
