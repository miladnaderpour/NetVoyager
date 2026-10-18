
"""Tests for discovery-relationship mapping and SQLite persistence."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from netvoyager_core.exceptions import NetVoyagerInvariantError
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.discovery.relationships import (
    DeviceDiscoveryCandidateRelationship,
)

from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities import (
    DeviceDiscoveryRelationshipEntity,
)
from netvoyager_database.entities.base import Base
from netvoyager_database.mappers.devices.discovery_candidate import (
    candidate_to_entity,
)
from netvoyager_database.mappers.devices.discovery_relationship import (
    relationship_to_domain,
    relationship_to_entity,
)
from netvoyager_database.session import create_session_factory


@pytest.fixture
def session_factory():
    """Provide an isolated SQLite database for each test."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def _create_candidates(session):
    """Insert two candidates before inserting their relationship."""
    first = DeviceDiscoveryCandidate(name="Excel firewall")
    second = DeviceDiscoveryCandidate(name="Panorama firewall")

    session.add_all(
        [
            candidate_to_entity(first),
            candidate_to_entity(second),
        ]
    )
    session.flush()

    return first, second


def test_relationship_mapping_preserves_identity():
    """Domain mapping must preserve deterministic relationship identity."""
    first_id = uuid4()
    second_id = uuid4()
    evidence_id = uuid4()

    relationship = DeviceDiscoveryCandidateRelationship(
        candidate_a_id=first_id,
        candidate_b_id=second_id,
        status="confirmed",
        evidence_ids=frozenset({evidence_id}),
    )

    restored = relationship_to_domain(
        relationship_to_entity(relationship)
    )

    assert restored == relationship
    assert restored.relationship_id == relationship.relationship_id
    assert restored.evidence_ids == frozenset({evidence_id})


def test_relationship_identity_is_symmetric():
    """Candidate order must not affect relationship identity."""
    first_id = uuid4()
    second_id = uuid4()

    first = DeviceDiscoveryCandidateRelationship(
        first_id,
        second_id,
    )
    second = DeviceDiscoveryCandidateRelationship(
        second_id,
        first_id,
    )

    assert first.relationship_id == second.relationship_id
    assert first.candidate_a_id == second.candidate_a_id
    assert first.candidate_b_id == second.candidate_b_id


def test_relationship_database_round_trip(session_factory):
    """Persist and reconstruct an evidence-backed relationship."""
    evidence_ids = frozenset({uuid4(), uuid4()})

    with session_factory() as session:
        first, second = _create_candidates(session)

        relationship = DeviceDiscoveryCandidateRelationship(
            first.candidate_id,
            second.candidate_id,
            status="confirmed",
            evidence_ids=evidence_ids,
        )

        session.add(relationship_to_entity(relationship))
        session.commit()

    with session_factory() as session:
        entity = session.get(
            DeviceDiscoveryRelationshipEntity,
            relationship.relationship_id,
        )

        assert entity is not None

        restored = relationship_to_domain(entity)

        assert restored == relationship
        assert restored.evidence_ids == evidence_ids
        assert entity.created_at is not None
        assert entity.updated_at is not None


def test_relationship_rejects_missing_candidates(session_factory):
    """Foreign keys must prevent orphan candidate relationships."""
    relationship = DeviceDiscoveryCandidateRelationship(
        uuid4(),
        uuid4(),
    )

    with session_factory() as session:
        session.add(relationship_to_entity(relationship))

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_relationship_rejects_duplicate_pair(session_factory):
    """A candidate pair must have only one stored relationship."""
    with session_factory() as session:
        first, second = _create_candidates(session)

        relationship = DeviceDiscoveryCandidateRelationship(
            first.candidate_id,
            second.candidate_id,
        )

        session.add(relationship_to_entity(relationship))
        session.commit()

    with session_factory() as session:
        duplicate = DeviceDiscoveryCandidateRelationship(
            second.candidate_id,
            first.candidate_id,
            status="rejected",
        )

        session.add(relationship_to_entity(duplicate))

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_relationship_rejects_corrupted_identity():
    """Stored relationship IDs must match domain identity rules."""
    relationship = DeviceDiscoveryCandidateRelationship(
        uuid4(),
        uuid4(),
    )

    entity = relationship_to_entity(relationship)
    entity.relationship_id = uuid4()

    with pytest.raises(NetVoyagerInvariantError) as error:
        relationship_to_domain(entity)

    assert error.value.code == (
        "database.discovery_relationship_identity_mismatch"
    )


def test_relationship_status_does_not_change_identity():
    """Relationship lifecycle status is separate from its UUID."""
    first_id = uuid4()
    second_id = uuid4()

    possible = DeviceDiscoveryCandidateRelationship(
        first_id,
        second_id,
        status="possible",
    )
    rejected = DeviceDiscoveryCandidateRelationship(
        first_id,
        second_id,
        status="rejected",
    )

    assert possible.relationship_id == rejected.relationship_id
    assert possible.status != rejected.status
