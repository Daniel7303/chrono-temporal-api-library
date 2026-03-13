from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.db import get_db
from demo.schemas import CustomerCreate, CustomerRead, PlanUpgrade
from demo.service import SubscriptionService

router = APIRouter(prefix="/demo/subscriptions", tags=["Demo - Subscription Management"])


@router.post("/customers", response_model=CustomerRead, status_code=201)
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)):
    """Create a new customer with a subscription plan."""
    svc = SubscriptionService(db)
    try:
        return await svc.create_customer(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Get the current state of a customer."""
    svc = SubscriptionService(db)
    customer = await svc.get_current(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/customers/{customer_id}/plan", response_model=CustomerRead)
async def upgrade_plan(
    customer_id: str,
    payload: PlanUpgrade,
    db: AsyncSession = Depends(get_db),
):
    """Upgrade or downgrade a customer's subscription plan."""
    svc = SubscriptionService(db)
    try:
        return await svc.upgrade_plan(customer_id, payload.new_plan, payload.effective_from)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers/{customer_id}/history", response_model=list[CustomerRead])
async def get_history(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full subscription history of a customer."""
    svc = SubscriptionService(db)
    return await svc.get_history(customer_id)


@router.get("/customers/{customer_id}/as-of", response_model=CustomerRead)
async def get_as_of(
    customer_id: str,
    as_of: datetime = Query(..., description="ISO 8601 datetime e.g. 2024-06-01T00:00:00Z"),
    db: AsyncSession = Depends(get_db),
):
    """What plan was this customer on at a specific point in time?"""
    svc = SubscriptionService(db)
    customer = await svc.get_at(customer_id, as_of)
    if not customer:
        raise HTTPException(status_code=404, detail="No record found at that point in time")
    return customer


@router.get("/customers/{customer_id}/diff")
async def get_diff(
    customer_id: str,
    from_dt: datetime = Query(..., description="Start datetime e.g. 2024-01-01T00:00:00Z"),
    to_dt: datetime = Query(..., description="End datetime e.g. 2025-01-01T00:00:00Z"),
    db: AsyncSession = Depends(get_db),
):
    """What changed in this customer's account between two dates?"""
    svc = SubscriptionService(db)
    return await svc.get_diff(customer_id, from_dt, to_dt)
