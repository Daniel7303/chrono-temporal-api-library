from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.api.v1 import api_router
from app.db import engine, Base
# Import models so Base knows about them
import app.models  # noqa

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic for production migrations)
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

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
