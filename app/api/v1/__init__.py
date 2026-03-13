from fastapi import APIRouter
from .endpoints.temporal import router as temporal_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(temporal_router)
