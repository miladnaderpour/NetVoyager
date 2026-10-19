
"""Tests for SQLAlchemy-native evidence-to-object relations."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from netvoyager_intelligence.evidence import EvidenceRecord, EvidenceRelation


def test_relation_uses_uuid_identifiers() -> None:
    """Store UUID evidence and domain-object identifiers."""
    evidence_id = uuid4()
    object_id = uuid4()

    relation = EvidenceRelation(
        evidence_id=evidence_id,
        object_type="network_device",
        object_id=object_id,
    )

    assert isinstance(relation.evidence_id, UUID)
    assert isinstance(relation.object_id, UUID)
    assert relation.evidence_id == evidence_id
    assert relation.object_id == object_id
    assert relation.object_type == "network_device"


def test_one_evidence_can_reference_multiple_objects(
    session_factory: sessionmaker[Session],
) -> None:
    """Link one evidence record to multiple domain objects."""
    record = EvidenceRecord(source="panorama", details={})
    evidence_id = record.id
    device_id = uuid4()
    scope_id = uuid4()

    with session_factory() as session:
        session.add(record)
        session.flush()
        session.add_all(
            [
                EvidenceRelation(evidence_id, "network_device", device_id),
                EvidenceRelation(evidence_id, "network_scope", scope_id),
            ]
        )
        session.commit()

    with session_factory() as session:
        relations = session.scalars(
            select(EvidenceRelation).where(
                EvidenceRelation.evidence_id == evidence_id
            )
        ).all()

        assert len(relations) == 2
        assert {r.object_id for r in relations} == {device_id, scope_id}


def test_one_object_can_have_multiple_evidence_records(
    session_factory: sessionmaker[Session],
) -> None:
    """Allow multiple evidence records for the same domain object."""
    object_id = uuid4()
    first = EvidenceRecord(source="excel", details={})
    second = EvidenceRecord(source="panorama", details={})
    first_id, second_id = first.id, second.id

    with session_factory() as session:
        session.add_all([first, second])
        session.flush()
        session.add_all(
            [
                EvidenceRelation(first_id, "network_device", object_id),
                EvidenceRelation(second_id, "network_device", object_id),
            ]
        )
        session.commit()

    with session_factory() as session:
        relations = session.scalars(
            select(EvidenceRelation).where(
                EvidenceRelation.object_id == object_id
            )
        ).all()

        assert len(relations) == 2
        assert {r.evidence_id for r in relations} == {first_id, second_id}


def test_duplicate_relation_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    """Enforce the composite evidence/object primary key."""
    record = EvidenceRecord(source="excel", details={})
    evidence_id = record.id
    object_id = uuid4()

    with session_factory() as session:
        session.add(record)
        session.flush()
        session.add(
            EvidenceRelation(evidence_id, "network_device", object_id)
        )
        session.commit()

    with session_factory() as session:
        session.add(
            EvidenceRelation(evidence_id, "network_device", object_id)
        )

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_relation_requires_existing_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject relations referencing unknown evidence records."""
    relation = EvidenceRelation(
        uuid4(),
        "network_device",
        uuid4(),
    )

    with session_factory() as session:
        session.add(relation)

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_relationship_navigation(
    session_factory: sessionmaker[Session],
) -> None:
    """Navigate from evidence to relations and back."""
    record = EvidenceRecord(source="excel", details={})
    evidence_id = record.id
    object_id = uuid4()

    with session_factory() as session:
        session.add(record)
        session.flush()
        session.add(
            EvidenceRelation(evidence_id, "network_device", object_id)
        )
        session.commit()

    with session_factory() as session:
        loaded = session.get(EvidenceRecord, evidence_id)

        assert loaded is not None
        assert len(loaded.relations) == 1
        assert loaded.relations[0].object_id == object_id
        assert loaded.relations[0].evidence is loaded


def test_same_object_uuid_can_have_different_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    """Preserve separate observations referencing one object UUID."""
    object_id = uuid4()
    records = [
        EvidenceRecord(source="excel", details={"run": 1}),
        EvidenceRecord(source="excel", details={"run": 2}),
    ]
    evidence_ids = {record.id for record in records}

    with session_factory() as session:
        session.add_all(records)
        session.flush()

        session.add_all(
            [
                EvidenceRelation(
                    record.id,
                    "network_device",
                    object_id,
                )
                for record in records
            ]
        )
        session.commit()

    with session_factory() as session:
        relations = session.scalars(
            select(EvidenceRelation).where(
                EvidenceRelation.object_id == object_id
            )
        ).all()

        assert {r.evidence_id for r in relations} == evidence_ids
