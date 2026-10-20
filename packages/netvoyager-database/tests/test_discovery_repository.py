
"""Integration tests for SQLAlchemy device-discovery persistence."""

from dataclasses import replace
from datetime import UTC, datetime
from ipaddress import IPv4Address
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from netvoyager_database.exceptions import (
    RepositoryConflictError,
    RepositoryNotFoundError,
    TransactionError,
)
from netvoyager_database.schema import create_schema
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_intelligence.evidence import EvidenceRecord
from netvoyager_network.device.discovery.decisions import (
    DeviceDiscoveryDecision,
)
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.discovery.relationships import (
    DeviceDiscoveryCandidateRelationship,
)


@pytest.fixture
def session_factory():
    """Create isolated sessions with the complete NetVoyager schema."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    create_schema(engine)

    try:
        yield sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )
    finally:
        engine.dispose()


def _candidate(
    name: str,
    *,
    serial: str | None = None,
    ip: str | None = None,
) -> DeviceDiscoveryCandidate:
    """Create an independent provisional device identity."""
    return DeviceDiscoveryCandidate(
        name=name,
        serial_number=serial,
        management_ip=IPv4Address(ip) if ip else None,
    )


def _decision(
    subject_id,
    *,
    subject_type="relationship",
    previous="possible",
    new="confirmed",
    actor_type="human",
    actor_id="entra:engineer-001",
) -> DeviceDiscoveryDecision:
    """Create an authorized discovery decision for testing."""
    return DeviceDiscoveryDecision(
        decision_type=(
            "relationship_status"
            if subject_type == "relationship"
            else "candidate_lifecycle"
        ),
        subject_id=subject_id,
        previous_value=previous,
        new_value=new,
        evidence_ids=(),
        reason="Authorized discovery review.",
        timestamp=datetime.now(UTC),
        subject_type=subject_type,
        actor_type=actor_type,
        actor_id=actor_id,
    )


def test_candidate_insert_and_lookup(session_factory) -> None:
    """Find a stored candidate by ID, name, serial, and IP."""
    candidate = _candidate(
        "SW-MAN-01",
        serial="FOC123456",
        ip="10.131.0.10",
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(candidate)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.discovery.get_candidate(candidate.candidate_id) == candidate
        assert uow.discovery.find_by_name("SW-MAN-01") == (candidate,)
        assert uow.discovery.find_by_serial("FOC123456") == (candidate,)
        assert uow.discovery.find_by_management_ip(
            IPv4Address("10.131.0.10")
        ) == (candidate,)


def test_multiple_candidates_can_share_attributes(session_factory) -> None:
    """Weak matching attributes must not consolidate candidate IDs."""
    first = _candidate("SW-MAN-01", serial="FOC123456")
    second = _candidate("SW-MAN-01", serial="FOC123456")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(first)
        uow.discovery.add_candidate(second)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        matches = uow.discovery.find_by_serial("FOC123456")
        assert {candidate.candidate_id for candidate in matches} == {
            first.candidate_id,
            second.candidate_id,
        }


def test_candidate_snapshot_update(session_factory) -> None:
    """Persist changes to an existing candidate without replacing its ID."""
    candidate = _candidate("SW-MAN-01")
    updated = replace(
        candidate,
        status="corroborated",
        serial_number="FOC123456",
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(candidate)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.save_candidate(updated)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.discovery.get_candidate(candidate.candidate_id) == updated


def test_candidate_duplicate_and_missing_update(session_factory) -> None:
    """Report duplicate inserts and updates of missing candidates."""
    candidate = _candidate("SW-MAN-01")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(candidate)
        uow.commit()

    with pytest.raises(RepositoryConflictError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.discovery.add_candidate(candidate)

    with pytest.raises(RepositoryNotFoundError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.discovery.save_candidate(_candidate("UNKNOWN"))


def test_relationship_lookup_and_update(session_factory) -> None:
    """Preserve relationship identity regardless of candidate order."""
    first = _candidate("SW-A")
    second = _candidate("SW-B")
    evidence_id = uuid4()

    relationship = DeviceDiscoveryCandidateRelationship(
        candidate_a_id=first.candidate_id,
        candidate_b_id=second.candidate_id,
        status="possible",
    )
    confirmed = DeviceDiscoveryCandidateRelationship(
        candidate_a_id=second.candidate_id,
        candidate_b_id=first.candidate_id,
        status="confirmed",
        evidence_ids=frozenset({evidence_id}),
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(first)
        uow.discovery.add_candidate(second)
        uow.discovery.add_relationship(relationship)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.discovery.find_relationship(
            second.candidate_id,
            first.candidate_id,
        ) == relationship
        assert uow.discovery.relationships_for_candidate(
            first.candidate_id
        ) == (relationship,)

        uow.discovery.save_relationship(confirmed)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.discovery.get_relationship(
            relationship.relationship_id
        ) == confirmed


def test_duplicate_relationship_and_missing_update(session_factory) -> None:
    """Reject duplicate relationship identity and missing updates."""
    first = _candidate("SW-A")
    second = _candidate("SW-B")

    relationship = DeviceDiscoveryCandidateRelationship(
        first.candidate_id,
        second.candidate_id,
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(first)
        uow.discovery.add_candidate(second)
        uow.discovery.add_relationship(relationship)
        uow.commit()

    with pytest.raises(RepositoryConflictError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.discovery.add_relationship(relationship)

    unknown = DeviceDiscoveryCandidateRelationship(
        uuid4(),
        uuid4(),
    )
    with pytest.raises(RepositoryNotFoundError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.discovery.save_relationship(unknown)


def test_decision_history_is_append_only(session_factory) -> None:
    """Preserve multiple decisions about the same relationship."""
    subject_id = uuid4()

    first = _decision(subject_id)
    second = _decision(
        subject_id,
        previous="confirmed",
        new="rejected",
        actor_type="ai_agent",
        actor_id="netvoyager-review-agent",
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.append_decision(first)
        uow.discovery.append_decision(second)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        history = uow.discovery.decisions_for(subject_id)

        assert len(history) == 2
        assert {decision.new_value for decision in history} == {
            "confirmed",
            "rejected",
        }
        assert {decision.actor_type for decision in history} == {
            "human",
            "ai_agent",
        }


def test_candidate_decision_and_evidence_commit_together(
    session_factory,
) -> None:
    """Commit candidate state, its decision, and evidence atomically."""
    candidate = _candidate("SW-MAN-01")
    evidence = EvidenceRecord(
        source="excel",
        details={"name": "SW-MAN-01"},
    )
    decision = _decision(
        candidate.candidate_id,
        subject_type="candidate",
        previous=None,
        new="candidate",
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(candidate)
        uow.evidence.add(evidence)
        uow.discovery.append_decision(decision)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.discovery.get_candidate(candidate.candidate_id) is not None
        assert uow.evidence.get(evidence.id) is not None
        assert uow.discovery.decisions_for(candidate.candidate_id) == (
            decision,
        )


def test_failure_rolls_back_discovery_and_evidence(session_factory) -> None:
    """Roll back pending discovery records when a later insert fails."""
    existing = _candidate("SW-EXISTING")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.discovery.add_candidate(existing)
        uow.commit()

    candidate = _candidate("SW-NEW")
    evidence = EvidenceRecord(source="excel", details={"row": 10})

    with pytest.raises(RepositoryConflictError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.discovery.add_candidate(candidate)
            uow.evidence.add(evidence)
            uow.discovery.add_candidate(existing)
            uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.discovery.get_candidate(candidate.candidate_id) is None
        assert uow.evidence.get(evidence.id) is None
        assert uow.discovery.get_candidate(existing.candidate_id) == existing


def test_discovery_requires_active_unit_of_work(session_factory) -> None:
    """Reject discovery repository access outside an active transaction."""
    uow = NetworkInventoryUnitOfWork(session_factory)

    with pytest.raises(TransactionError):
        _ = uow.discovery
