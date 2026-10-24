"""Tests for pure prefix discovery identity comparison."""

from dataclasses import replace
from ipaddress import IPv4Network, IPv6Network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.discovery.matching import (
    compare_prefix_observation,
)
from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)


def observation(prefix, address_space_id=None):
    return PrefixObservation(
        local_ref="synthetic-prefix",
        prefix=prefix,
        observation_kind="inventory",
        address_space_id=address_space_id,
    )


def candidate(prefix, address_space_id=None):
    return PrefixDiscoveryCandidate(
        prefix=prefix,
        address_space_id=address_space_id,
    )


def test_same_prefix_and_space_exact_match():
    space_id = uuid4()
    prefix = IPv4Network("192.0.2.0/24")

    result = compare_prefix_observation(
        observation(prefix, space_id),
        candidate(prefix, space_id),
    )

    assert result is not None
    assert result.strength == "exact"


@pytest.mark.parametrize(
    "observed_known,candidate_known",
    [(True, False), (False, True), (False, False)],
)
def test_unknown_space_does_not_match_on_cidr_alone(
    observed_known,
    candidate_known,
):
    space_id = uuid4()
    prefix = IPv4Network("192.0.2.0/24")

    result = compare_prefix_observation(
        observation(prefix, space_id if observed_known else None),
        candidate(prefix, space_id if candidate_known else None),
    )

    assert result is None


def test_different_known_spaces_do_not_match():
    prefix = IPv4Network("192.0.2.0/24")

    result = compare_prefix_observation(
        observation(prefix, uuid4()),
        candidate(prefix, uuid4()),
    )

    assert result is None


def test_different_prefixes_do_not_match():
    space_id = uuid4()

    result = compare_prefix_observation(
        observation(IPv4Network("192.0.2.0/24"), space_id),
        candidate(IPv4Network("198.51.100.0/24"), space_id),
    )

    assert result is None


def test_containing_prefix_is_not_identity_match():
    space_id = uuid4()

    result = compare_prefix_observation(
        observation(IPv4Network("192.0.2.0/25"), space_id),
        candidate(IPv4Network("192.0.2.0/24"), space_id),
    )

    assert result is None


def test_equivalent_normalized_prefixes_match():
    space_id = uuid4()

    result = compare_prefix_observation(
        observation(
            IPv4Network("192.0.2.1/24", strict=False),
            space_id,
        ),
        candidate(
            IPv4Network("192.0.2.0/24"),
            space_id,
        ),
    )

    assert result is not None
    assert result.strength == "exact"


def test_ipv6_prefix_match():
    space_id = uuid4()
    prefix = IPv6Network("2001:db8::/64")

    result = compare_prefix_observation(
        observation(prefix, space_id),
        candidate(prefix, space_id),
    )

    assert result is not None
    assert result.strength == "exact"


@pytest.mark.parametrize("status", ["rejected", "retired"])
def test_inactive_candidate_not_matched(status):
    prefix = IPv4Network("192.0.2.0/24")
    space_id = uuid4()
    existing = candidate(prefix, space_id)
    existing = replace(existing, status=status)

    result = compare_prefix_observation(
        observation(prefix, space_id),
        existing,
    )

    assert result is None


def test_comparison_does_not_mutate_candidate():
    prefix = IPv4Network("192.0.2.0/24")
    space_id = uuid4()
    existing = candidate(prefix, space_id)
    original_id = existing.candidate_id

    result = compare_prefix_observation(
        observation(prefix, space_id),
        existing,
    )

    assert result is not None
    assert existing.candidate_id == original_id
    assert existing.status == "candidate"
    assert existing.resolved_prefix_id is None