
"""Tests for non-destructive prefix candidate correlation."""

from dataclasses import replace
from ipaddress import IPv4Network, IPv6Network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.discovery.correlation import (
    correlate_prefix_candidates,
)
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
)


def candidate(
    prefix="192.0.2.0/24",
    *,
    space=None,
    status="candidate",
):
    network = (
        IPv6Network(prefix)
        if ":" in prefix
        else IPv4Network(prefix)
    )
    return PrefixDiscoveryCandidate(
        prefix=network,
        address_space_id=space,
        status=status,
    )


def test_equal_prefix_and_space_proposes_possible():
    space = uuid4()
    first = candidate(space=space)
    second = candidate(space=space)

    result = correlate_prefix_candidates([first, second])

    assert len(result.proposed) == 1
    assert result.proposed[0].status == "possible"


def test_unknown_space_allows_provisional_correlation():
    first = candidate(space=uuid4())
    second = candidate()

    result = correlate_prefix_candidates([first, second])

    assert len(result.proposed) == 1


def test_different_known_spaces_are_not_correlated():
    first = candidate(space=uuid4())
    second = candidate(space=uuid4())

    result = correlate_prefix_candidates([first, second])

    assert result.proposed == ()


def test_different_prefixes_are_not_correlated():
    first = candidate("192.0.2.0/24")
    second = candidate("198.51.100.0/24")

    result = correlate_prefix_candidates([first, second])

    assert result.proposed == ()


def test_existing_rejected_relationship_is_preserved():
    first = candidate()
    second = candidate()

    rejected = PrefixDiscoveryCandidateRelationship(
        first.candidate_id,
        second.candidate_id,
        status="rejected",
    )

    result = correlate_prefix_candidates(
        [first, second],
        [rejected],
    )

    assert result.proposed == ()
    assert rejected.status == "rejected"


def test_existing_confirmed_relationship_is_not_duplicated():
    first = candidate()
    second = candidate()

    confirmed = PrefixDiscoveryCandidateRelationship(
        first.candidate_id,
        second.candidate_id,
        status="confirmed",
    )

    result = correlate_prefix_candidates(
        [first, second],
        [confirmed],
    )

    assert result.proposed == ()


def test_duplicate_candidates_do_not_create_self_relationship():
    first = candidate()

    result = correlate_prefix_candidates([first, first])

    assert result.proposed == ()


def test_inactive_candidates_are_excluded():
    active = candidate()
    rejected = candidate(status="rejected")
    retired = candidate(status="retired")

    result = correlate_prefix_candidates(
        [active, rejected, retired]
    )

    assert result.proposed == ()


def test_ipv6_correlation():
    space = uuid4()
    first = candidate("2001:db8::/64", space=space)
    second = candidate("2001:db8::/64", space=space)

    result = correlate_prefix_candidates([first, second])

    assert len(result.proposed) == 1


def test_correlation_is_order_independent():
    candidates = [candidate() for _ in range(3)]

    forward = correlate_prefix_candidates(candidates)
    reverse = correlate_prefix_candidates(reversed(candidates))

    assert forward == reverse
    assert len(forward.proposed) == 3


def test_conflicting_candidate_snapshots_are_rejected():
    original = candidate()
    changed = replace(
        original,
        prefix=IPv4Network("198.51.100.0/24"),
    )

    with pytest.raises(ValueError):
        correlate_prefix_candidates([original, changed])


def test_correlation_does_not_mutate_candidates():
    first = candidate()
    second = candidate()

    result = correlate_prefix_candidates([first, second])

    assert len(result.proposed) == 1
    assert first.status == "candidate"
    assert second.status == "candidate"
    assert first.resolved_prefix_id is None
    assert second.resolved_prefix_id is None
