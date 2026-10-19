
"""Tests for SQLAlchemy-native evidence provenance records."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import null, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from netvoyager_intelligence.evidence import EvidenceRecord


def test_record_generates_identity_and_timestamp() -> None:
    """Assign identity and creation time before persistence."""
    record = EvidenceRecord(source="excel", details={"row": 10})

    assert isinstance(record.id, UUID)
    assert record.created_at.tzinfo is not None
    assert record.source == "excel"
    assert record.details == {"row": 10}


def test_record_preserves_explicit_identity_and_timestamp() -> None:
    """Preserve supplied identity and creation time."""
    identifier = uuid4()
    timestamp = datetime(2026, 10, 19, tzinfo=timezone.utc)

    record = EvidenceRecord(
        source="excel",
        details={},
        id=identifier,
        created_at=timestamp,
    )

    assert record.id == identifier
    assert record.created_at == timestamp


def test_record_round_trip(
    session_factory: sessionmaker[Session],
) -> None:
    """Persist and reload JSON-compatible provenance details."""
    details = {
        "row": 10,
        "hostname": "switch-01",
        "management_ip": "10.131.0.10",
        "active": True,
        "tags": ["network", "managed"],
        "metadata": {"source": "inventory"},
    }

    record = EvidenceRecord(source="excel_inventory", details=details)
    evidence_id = record.id

    with session_factory() as session:
        session.add(record)
        session.commit()

    with session_factory() as session:
        loaded = session.get(EvidenceRecord, evidence_id)

        assert loaded is not None
        assert loaded.id == evidence_id
        assert loaded.source == "excel_inventory"
        assert loaded.details == details


def test_multiple_identical_observations_remain_distinct(
    session_factory: sessionmaker[Session],
) -> None:
    """Retain independent evidence IDs for identical observations."""
    first = EvidenceRecord(
        source="excel",
        details={"hostname": "switch-01"},
    )
    second = EvidenceRecord(
        source="excel",
        details={"hostname": "switch-01"},
    )

    first_id = first.id
    second_id = second.id

    assert first_id != second_id

    with session_factory() as session:
        session.add_all([first, second])
        session.commit()

    with session_factory() as session:
        records = session.scalars(
            select(EvidenceRecord).where(
                EvidenceRecord.id.in_((first_id, second_id))
            )
        ).all()

        assert len(records) == 2
        assert {record.id for record in records} == {first_id, second_id}


def test_record_requires_source(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject a SQL NULL source."""
    record = EvidenceRecord(
        source=None,  # type: ignore[arg-type]
        details={},
    )

    with session_factory() as session:
        session.add(record)

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_record_requires_details(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject SQL NULL in the required details column."""
    record = EvidenceRecord(source="excel", details={})

    with session_factory() as session:
        session.add(record)
        session.flush()

        with pytest.raises(IntegrityError):
            session.execute(
                update(EvidenceRecord)
                .where(EvidenceRecord.id == record.id)
                .values(details=null())
            )

        session.rollback()


def test_duplicate_record_identity_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject duplicate evidence primary keys."""
    identifier = uuid4()

    with session_factory() as session:
        session.add(
            EvidenceRecord(source="excel", details={}, id=identifier)
        )
        session.commit()

    with session_factory() as session:
        session.add(
            EvidenceRecord(source="panorama", details={}, id=identifier)
        )

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_uncommitted_record_is_rolled_back(
    session_factory: sessionmaker[Session],
) -> None:
    """Discard evidence when the transaction is not committed."""
    record = EvidenceRecord(source="excel", details={"row": 5})
    evidence_id = record.id

    with session_factory() as session:
        session.add(record)
        session.flush()

    with session_factory() as session:
        assert session.get(EvidenceRecord, evidence_id) is None
