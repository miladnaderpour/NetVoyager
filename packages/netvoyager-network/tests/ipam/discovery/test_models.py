
"""Synthetic prefix discovery domain tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from ipaddress import IPv4Network, IPv6Network
from uuid import uuid4

import pytest

from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
)
from netvoyager_network.ipam.discovery.decisions import (
    PrefixDiscoveryDecision,
)


def test_candidate_identity_independent_of_attributes():
    first = PrefixDiscoveryCandidate(
        prefix=IPv4Network("192.0.2.0/24")
    )
    second = PrefixDiscoveryCandidate(
        prefix=IPv4Network("192.0.2.0/24")
    )

    assert first.candidate_id != second.candidate_id
    assert first.address_space_id is None


def test_ipv6_and_address_space_hypothesis():
    candidate = PrefixDiscoveryCandidate(
        prefix=IPv6Network("2001:db8::/64"),
        address_space_id=uuid4(),
    )

    assert candidate.prefix.version == 6


def test_resolved_requires_reference():
    with pytest.raises(ValueError):
        PrefixDiscoveryCandidate(status="resolved")

    with pytest.raises(ValueError):
        PrefixDiscoveryCandidate(resolved_prefix_id=uuid4())

    candidate = PrefixDiscoveryCandidate(
        status="resolved",
        resolved_prefix_id=uuid4(),
    )
    assert candidate.resolved_prefix_id is not None


def test_candidate_rejects_bad_fields_and_time():
    with pytest.raises(TypeError):
        PrefixDiscoveryCandidate(prefix="192.0.2.0/24")

    with pytest.raises(TypeError):
        PrefixDiscoveryCandidate(address_space_id="global")

    with pytest.raises(ValueError):
        PrefixDiscoveryCandidate(status="other")

    with pytest.raises(ValueError):
        PrefixDiscoveryCandidate(first_seen=datetime(2026, 1, 1))

    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        PrefixDiscoveryCandidate(
            first_seen=now,
            last_seen=now - timedelta(seconds=1),
        )


def test_candidate_snapshot_immutable():
    candidate = PrefixDiscoveryCandidate()

    with pytest.raises(Exception):
        candidate.status = "resolved"

    updated = replace(candidate, status="corroborated")
    assert updated.candidate_id == candidate.candidate_id


def test_relationship_symmetric_identity_and_evidence():
    first_id, second_id, evidence_id = uuid4(), uuid4(), uuid4()

    first = PrefixDiscoveryCandidateRelationship(
        first_id,
        second_id,
        evidence_ids=frozenset({evidence_id}),
    )
    second = PrefixDiscoveryCandidateRelationship(
        second_id,
        first_id,
        status="confirmed",
    )

    assert first.relationship_id == second.relationship_id
    assert first.evidence_ids == frozenset({evidence_id})
    assert first.status == "possible"
    assert second.status == "confirmed"


def test_relationship_rejects_self_and_bad_status():
    candidate_id = uuid4()

    with pytest.raises(ValueError):
        PrefixDiscoveryCandidateRelationship(
            candidate_id, candidate_id
        )

    with pytest.raises(ValueError):
        PrefixDiscoveryCandidateRelationship(
            candidate_id, uuid4(), status="invalid"
        )


def test_decision_audits_accepted_action():
    decision = PrefixDiscoveryDecision(
        decision_type="candidate_resolution",
        subject_id=uuid4(),
        previous_value="candidate",
        new_value="resolved",
        evidence_ids=(),
        reason="verified",
        timestamp=datetime.now(timezone.utc),
        subject_type="candidate",
        actor_type="human",
        actor_id="engineer",
    )

    assert decision.actor_id == "engineer"


def test_decision_rejects_bad_audit():
    values = dict(
        decision_type="candidate_lifecycle",
        subject_id=uuid4(),
        previous_value=None,
        new_value="candidate",
        evidence_ids=(),
        reason=None,
        timestamp=datetime.now(timezone.utc),
        subject_type="candidate",
        actor_type="system",
        actor_id="collector",
    )

    with pytest.raises(ValueError):
        PrefixDiscoveryDecision(**(values | {"actor_id": " "}))

    with pytest.raises(ValueError):
        PrefixDiscoveryDecision(
            **(values | {"timestamp": datetime(2026, 1, 1)})
        )
