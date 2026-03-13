import pytest
from datetime import datetime, timezone
from app.schemas.temporal_record import TemporalRecordCreate


def test_schema_valid_range_validation():
    """valid_to must be after valid_from."""
    with pytest.raises(ValueError):
        TemporalRecordCreate(
            entity_type="employee",
            entity_id="emp-001",
            valid_from=datetime(2024, 6, 1, tzinfo=timezone.utc),
            valid_to=datetime(2024, 1, 1, tzinfo=timezone.utc),  # before valid_from
            data={"name": "Alice"},
        )


def test_schema_valid_no_end_date():
    """valid_to=None means currently valid — should not raise."""
    record = TemporalRecordCreate(
        entity_type="employee",
        entity_id="emp-001",
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
        data={"name": "Alice"},
    )
    assert record.entity_id == "emp-001"
