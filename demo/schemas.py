from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class CustomerCreate(BaseModel):
    name: str
    email: str
    plan: str = "free"  # free, pro, enterprise


class CustomerRead(BaseModel):
    customer_id: str
    name: str
    email: str
    plan: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    record_id: int

    class Config:
        from_attributes = True


class PlanUpgrade(BaseModel):
    new_plan: str
    effective_from: Optional[datetime] = None  # defaults to now


class DiffRequest(BaseModel):
    from_dt: datetime
    to_dt: datetime


VALID_PLANS = ["free", "pro", "enterprise"]
