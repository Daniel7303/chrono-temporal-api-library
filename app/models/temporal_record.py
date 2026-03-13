from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, func
from sqlalchemy.dialects.postgresql import TSTZRANGE
from app.db.base import Base


class TemporalRecord(Base):
    """
    Core temporal record model.
    valid_from / valid_to: application-time (when the fact was true in reality)
    created_at / updated_at: transaction-time (when we recorded it)
    """
    __tablename__ = "temporal_records"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)

    # Application time (bi-temporal: valid time)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)  # NULL = currently valid

    # Transaction time (auto-managed)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Payload
    data = Column(JSON, nullable=False)
    notes = Column(Text, nullable=True)
