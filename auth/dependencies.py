from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from fastapi import Depends
from auth.service import APIKeyService

# This tells FastAPI to look for the key in the X-API-Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency that protects any route.
    Usage: add `dependencies=[Depends(require_api_key)]` to any router or endpoint.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include it in the X-API-Key header.",
        )

    svc = APIKeyService(db)
    is_valid = await svc.validate_key(api_key)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
        )
