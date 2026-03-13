from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.db.base import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)           # e.g. "production", "testing"
    hashed_key = Column(String(255), nullable=False, unique=True)
    prefix = Column(String(20), nullable=False)          # first 8 chars for identification
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
