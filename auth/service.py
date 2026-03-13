import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from auth.models import APIKey
from auth.schemas import APIKeyCreate, APIKeyCreated, APIKeyRead


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key for safe storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_raw_key() -> str:
    """Generate a secure random API key with a recognizable prefix."""
    token = secrets.token_hex(32)
    return f"chron_sk_{token}"


class APIKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_key(self, payload: APIKeyCreate) -> APIKeyCreated:
        """Generate a new API key. The raw key is returned only once."""
        raw_key = _generate_raw_key()
        hashed = _hash_key(raw_key)
        prefix = raw_key[:16]  # store first 16 chars for identification

        key = APIKey(
            name=payload.name,
            hashed_key=hashed,
            prefix=prefix,
            is_active=True,
        )
        self.db.add(key)
        await self.db.flush()
        await self.db.refresh(key)

        return APIKeyCreated(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            is_active=key.is_active,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            raw_key=raw_key,  # only time this is returned
        )

    async def list_keys(self) -> list[APIKeyRead]:
        """List all API keys (without raw values)."""
        result = await self.db.execute(
            select(APIKey).order_by(APIKey.created_at.desc())
        )
        return result.scalars().all()

    async def revoke_key(self, key_id: int) -> bool:
        """Deactivate an API key."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            return False
        key.is_active = False
        await self.db.flush()
        return True

    async def validate_key(self, raw_key: str) -> bool:
        """Check if a raw API key is valid and active. Updates last_used_at."""
        hashed = _hash_key(raw_key)
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.hashed_key == hashed,
                APIKey.is_active == True,
            )
        )
        key = result.scalar_one_or_none()
        if not key:
            return False

        # Update last used timestamp
        key.last_used_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True
