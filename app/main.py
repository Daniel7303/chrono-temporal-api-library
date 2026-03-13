from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.api.v1 import api_router
from app.db import engine, Base
from demo.router import router as demo_router
from auth.router import router as auth_router
from auth.dependencies import require_api_key
from fastapi import Depends
# Import models so Base knows about them
import app.models  # noqa
import auth.models  # noqa — registers APIKey model with Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Public routes — no auth required
app.include_router(auth_router)

# Protected routes — require valid API key
app.include_router(api_router, dependencies=[Depends(require_api_key)])
app.include_router(demo_router, dependencies=[Depends(require_api_key)])


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
