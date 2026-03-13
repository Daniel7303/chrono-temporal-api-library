from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.services.temporal_service import TemporalService
from app.schemas.temporal_record import TemporalRecordCreate
from demo.schemas import CustomerCreate, CustomerRead, VALID_PLANS


ENTITY_TYPE = "customer"


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.temporal = TemporalService(db)

    def _make_customer_id(self) -> str:
        return f"cust_{uuid.uuid4().hex[:8]}"

    def _record_to_customer(self, record) -> CustomerRead:
        return CustomerRead(
            customer_id=record.entity_id,
            name=record.data["name"],
            email=record.data["email"],
            plan=record.data["plan"],
            valid_from=record.valid_from,
            valid_to=record.valid_to,
            record_id=record.id,
        )

    async def create_customer(self, payload: CustomerCreate) -> CustomerRead:
        """Create a new customer on a plan."""
        if payload.plan not in VALID_PLANS:
            raise ValueError(f"Invalid plan. Choose from: {VALID_PLANS}")

        customer_id = self._make_customer_id()
        now = datetime.now(timezone.utc)

        record = await self.temporal.create(
            TemporalRecordCreate(
                entity_type=ENTITY_TYPE,
                entity_id=customer_id,
                valid_from=now,
                valid_to=None,
                data={
                    "name": payload.name,
                    "email": payload.email,
                    "plan": payload.plan,
                },
                notes=f"Customer created on {payload.plan} plan",
            )
        )
        return self._record_to_customer(record)

    async def get_current(self, customer_id: str) -> Optional[CustomerRead]:
        """Get current state of a customer."""
        records = await self.temporal.get_current(ENTITY_TYPE, customer_id)
        if not records:
            return None
        return self._record_to_customer(records[0])

    async def upgrade_plan(
        self, customer_id: str, new_plan: str, effective_from: Optional[datetime] = None
    ) -> CustomerRead:
        """Upgrade or downgrade a customer's plan."""
        if new_plan not in VALID_PLANS:
            raise ValueError(f"Invalid plan. Choose from: {VALID_PLANS}")

        effective_from = effective_from or datetime.now(timezone.utc)

        # Get current record
        current_records = await self.temporal.get_current(ENTITY_TYPE, customer_id)
        if not current_records:
            raise ValueError(f"Customer {customer_id} not found")

        current = current_records[0]

        # Close the current record
        await self.temporal.close_record(current.id, effective_from)

        # Create new record with updated plan
        new_record = await self.temporal.create(
            TemporalRecordCreate(
                entity_type=ENTITY_TYPE,
                entity_id=customer_id,
                valid_from=effective_from,
                valid_to=None,
                data={
                    "name": current.data["name"],
                    "email": current.data["email"],
                    "plan": new_plan,
                },
                notes=f"Plan changed from {current.data['plan']} to {new_plan}",
            )
        )
        return self._record_to_customer(new_record)

    async def get_history(self, customer_id: str) -> list[CustomerRead]:
        """Get the full plan history of a customer."""
        records = await self.temporal.get_history(ENTITY_TYPE, customer_id)
        return [self._record_to_customer(r) for r in records]

    async def get_at(self, customer_id: str, as_of: datetime) -> Optional[CustomerRead]:
        """Get customer state at a specific point in time."""
        records = await self.temporal.get_at_point_in_time(ENTITY_TYPE, customer_id, as_of)
        if not records:
            return None
        return self._record_to_customer(records[0])

    async def get_diff(self, customer_id: str, from_dt: datetime, to_dt: datetime) -> dict:
        """Diff a customer's state between two points in time."""
        return await self.temporal.get_diff(ENTITY_TYPE, customer_id, from_dt, to_dt)
