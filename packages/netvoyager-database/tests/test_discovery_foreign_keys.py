
"""Integration tests for discovery foreign keys and transaction rollback.

Verify that discovery relationships cannot reference missing candidates,
that resolved candidates reference existing canonical devices, and
that failed discovery operations roll back other repository writes.
"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from netvoyager_database.engine import create_database_engine
from netvoyager_database.exceptions import RepositoryConflictError
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_intelligence.evidence import EvidenceRecord
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.discovery.relationships import (
    DeviceDiscoveryCandidateRelationship,
)
from netvoyager_network.device.models import NetworkDevice


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """Provide an isolated SQLite database with foreign keys enabled."""
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def test_sqlite_foreign_keys_are_enabled(
    session_factory: sessionmaker[Session],
) -> None:
    """Verify that SQLite enforces foreign-key constraints."""
    with session_factory() as session:
        enabled = session.scalar(text("PRAGMA foreign_keys"))

    assert enabled == 1


def test_multiple_candidates_resolve_to_one_canonical_device(
    session_factory: sessionmaker[Session],
) -> None:
    """Preserve separate candidate identities for one canonical device."""
    device = NetworkDevice(name="SW-MAN-01")

    first = DeviceDiscoveryCandidate(
        name="SW-MAN-01",
        status="resolved",
        resolved_device_id=device.device_id,
    )
    second = DeviceDiscoveryCandidate(
        name="SW-MAN-01.local",
        status="resolved",
        resolved_device_id=device.device_id,
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(device)
        uow.discovery.add_candidate(first)
        uow.discovery.add_candidate(second)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        candidates = uow.discovery.candidates_for_device(
            device.device_id
        )

        assert len(candidates) == 2
        assert {candidate.candidate_id for candidate in candidates} == {
            first.candidate_id,
            second.candidate_id,
        }
        assert all(
            candidate.resolved_device_id == device.device_id
            for candidate in candidates
        )


def test_candidate_cannot_resolve_to_missing_device(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject a resolution referencing a nonexistent canonical device."""
    candidate = DeviceDiscoveryCandidate(
        name="UNKNOWN-SWITCH",
        status="resolved",
        resolved_device_id=uuid4(),
    )

    with pytest.raises(RepositoryConflictError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.discovery.add_candidate(candidate)
            uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert (
            uow.discovery.get_candidate(candidate.candidate_id)
            is None
        )


def test_relationship_cannot_reference_missing_candidates(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject an orphan relationship through database foreign keys."""
    relationship = DeviceDiscoveryCandidateRelationship(
        candidate_a_id=uuid4(),
        candidate_b_id=uuid4(),
    )

    with pytest.raises(RepositoryConflictError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.discovery.add_relationship(relationship)
            uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert (
            uow.discovery.get_relationship(
                relationship.relationship_id
            )
            is None
        )


def test_relationship_failure_rolls_back_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    """Roll back evidence when a discovery relationship insert fails."""
    evidence = EvidenceRecord(
        source="excel",
        details={"hostname": "SW-MAN-01"},
    )
    evidence_id = evidence.id

    relationship = DeviceDiscoveryCandidateRelationship(
        candidate_a_id=uuid4(),
        candidate_b_id=uuid4(),
    )

    with pytest.raises(RepositoryConflictError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.evidence.add(evidence)
            uow.discovery.add_relationship(relationship)
            uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.evidence.get(evidence_id) is None
        assert (
            uow.discovery.get_relationship(
                relationship.relationship_id
            )
            is None
        )
