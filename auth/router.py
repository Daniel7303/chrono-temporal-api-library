from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from auth.schemas import APIKeyCreate, APIKeyCreated, APIKeyRead
from auth.service import APIKeyService

router = APIRouter(prefix="/auth/keys", tags=["Authentication"])


@router.post("/", response_model=APIKeyCreated, status_code=201)
async def create_key(payload: APIKeyCreate, db: AsyncSession = Depends(get_db)):
    """
    Generate a new API key.
    ⚠️ The full key is only shown ONCE — store it immediately.
    """
    svc = APIKeyService(db)
    return await svc.create_key(payload)


@router.get("/", response_model=list[APIKeyRead])
async def list_keys(db: AsyncSession = Depends(get_db)):
    """List all API keys. Raw key values are never returned."""
    svc = APIKeyService(db)
    return await svc.list_keys()


@router.delete("/{key_id}", status_code=204)
async def revoke_key(key_id: int, db: AsyncSession = Depends(get_db)):
    """Revoke an API key by ID. This cannot be undone."""
    svc = APIKeyService(db)
    success = await svc.revoke_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
