
"""SQLite integration tests for prefix discovery persistence."""

from dataclasses import replace
from datetime import datetime, timezone
from ipaddress import IPv4Network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
)
from netvoyager_network.ipam.discovery.decisions import (
    PrefixDiscoveryDecision,
)
from netvoyager_database.engine import create_database_engine
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.repositories.prefix_discovery import (
    SqlPrefixDiscoveryRepository,
)


@pytest.fixture
def storage():
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)

    try:
        yield factory
    finally:
        engine.dispose()


def _observation(space=None):
    return PrefixObservation(
        local_ref="synthetic-1",
        prefix=IPv4Network("192.0.2.0/24"),
        observation_kind="inventory",
        address_space_id=space,
    )


def _candidate(space=None):
    return PrefixDiscoveryCandidate(
        prefix=IPv4Network("192.0.2.0/24"),
        address_space_id=space,
    )


def test_roundtrip_and_idempotent_link(storage):
    space = uuid4()
    dataset = uuid4()
    obs = _observation(space)
    cand = _candidate(space)

    with storage() as session:
        repo = SqlPrefixDiscoveryRepository(session)
        repo.add_observation(obs, dataset)
        repo.add_candidate(cand)
        repo.link_observation(obs.observation_id, cand.candidate_id)
        repo.link_observation(obs.observation_id, cand.candidate_id)
        session.commit()

    with storage() as session:
        repo = SqlPrefixDiscoveryRepository(session)

        assert repo.get_observation(obs.observation_id) == obs
        assert repo.get_candidate(cand.candidate_id) == cand
        assert repo.candidate_observation_ids(
            cand.candidate_id
        ) == (obs.observation_id,)
        assert repo.find_candidates(
            "192.0.2.1/24", space
        ) == (cand,)


def test_relationship_symmetry_and_decision_history(storage):
    a, b = _candidate(), _candidate()

    relationship = PrefixDiscoveryCandidateRelationship(
        a.candidate_id,
        b.candidate_id,
    )

    decision = PrefixDiscoveryDecision(
        decision_type="relationship_status",
        subject_type="relationship",
        subject_id=relationship.relationship_id,
        actor_type="human",
        actor_id="synthetic-engineer",
        previous_value=None,
        new_value="possible",
        evidence_ids=(),
        reason="review",
        timestamp=datetime.now(timezone.utc),
    )

    with storage() as session:
        repo = SqlPrefixDiscoveryRepository(session)

        repo.add_candidate(a)
        repo.add_candidate(b)
        repo.add_relationship(relationship)
        repo.append_decision(decision)
        repo.save_relationship(
            replace(relationship, status="confirmed")
        )
        session.commit()

    with storage() as session:
        repo = SqlPrefixDiscoveryRepository(session)

        assert repo.find_relationship(
            b.candidate_id,
            a.candidate_id,
        ).status == "confirmed"

        assert repo.decisions_for(
            relationship.relationship_id
        ) == (decision,)


def test_rollback_removes_uncommitted_candidates(storage):
    candidate = _candidate()

    with storage() as session:
        SqlPrefixDiscoveryRepository(session).add_candidate(
            candidate
        )
        session.rollback()

    with storage() as session:
        repo = SqlPrefixDiscoveryRepository(session)
        assert repo.get_candidate(
            candidate.candidate_id
        ) is None


def test_resolution_blocked_before_canonical_prefix_persistence(
    storage,
):
    candidate = _candidate()

    with storage() as session:
        repo = SqlPrefixDiscoveryRepository(session)
        repo.add_candidate(candidate)

        with pytest.raises(ValueError):
            repo.save_candidate(
                replace(
                    candidate,
                    status="resolved",
                    resolved_prefix_id=uuid4(),
                )
            )
