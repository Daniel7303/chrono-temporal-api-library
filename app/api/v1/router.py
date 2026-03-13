from fastapi import APIRouter
from app.api.v1.endpoints import temporal_records

api_router = APIRouter()
api_router.include_router(temporal_records.router)
