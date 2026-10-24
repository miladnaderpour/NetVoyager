"""Tests for non-mutating prefix observation assignment planning."""

from dataclasses import replace
from ipaddress import IPv4Network, IPv6Network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.discovery.planning import (
    plan_prefix_observation_assignment,
)
from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)


def observed(prefix="192.0.2.0/24", space=None):
    network = IPv6Network(prefix) if ":" in prefix else IPv4Network(prefix)
    return PrefixObservation(
        local_ref="source-entry",
        prefix=network,
        observation_kind="inventory",
        address_space_id=space,
    )


def candidate(prefix="192.0.2.0/24", space=None):
    network = IPv6Network(prefix) if ":" in prefix else IPv4Network(prefix)
    return PrefixDiscoveryCandidate(
        prefix=network,
        address_space_id=space,
    )


def test_one_exact_match_reuses_candidate():
    space = uuid4()
    existing = candidate(space=space)

    result = plan_prefix_observation_assignment(
        observed(space=space),
        [existing],
    )

    assert result.action == "reuse_candidate"
    assert result.candidate is existing
    assert result.possible_matches == ()


def test_missing_candidate_proposes_new_one():
    item = observed()

    result = plan_prefix_observation_assignment(item, [])

    assert result.action == "create_candidate"
    assert result.candidate.candidate_id.version == 4
    assert result.candidate.address_space_id is None
    assert result.observation_id == item.observation_id


@pytest.mark.parametrize(
    "observed_known,candidate_known",
    [(True, False), (False, True), (False, False)],
)
def test_unknown_address_space_keeps_candidates_separate(
    observed_known,
    candidate_known,
):
    space = uuid4()
    existing = candidate(
        space=space if candidate_known else None,
    )

    result = plan_prefix_observation_assignment(
        observed(space=space if observed_known else None),
        [existing],
    )

    assert result.action == "create_candidate"
    assert result.candidate.candidate_id != existing.candidate_id
    assert result.possible_matches == ()


def test_multiple_exact_matches_do_not_choose_arbitrarily():
    space = uuid4()
    left = candidate(space=space)
    right = candidate(space=space)

    result = plan_prefix_observation_assignment(
        observed(space=space),
        [left, right],
    )

    assert result.action == "create_candidate"
    assert {
        match.candidate_id for match in result.possible_matches
    } == {left.candidate_id, right.candidate_id}


def test_other_known_space_not_a_match():
    result = plan_prefix_observation_assignment(
        observed(space=uuid4()),
        [candidate(space=uuid4())],
    )

    assert result.action == "create_candidate"
    assert result.possible_matches == ()


def test_rejected_candidates_not_reused():
    space = uuid4()
    rejected = replace(candidate(space=space), status="rejected")

    result = plan_prefix_observation_assignment(
        observed(space=space),
        [rejected],
    )

    assert result.action == "create_candidate"
    assert result.possible_matches == ()


def test_ipv6_exact_match():
    space = uuid4()
    existing = candidate("2001:db8::/64", space)

    result = plan_prefix_observation_assignment(
        observed("2001:db8::/64", space),
        [existing],
    )

    assert result.action == "reuse_candidate"


def test_duplicate_candidate_is_deduplicated():
    space = uuid4()
    existing = candidate(space=space)

    result = plan_prefix_observation_assignment(
        observed(space=space),
        [existing, existing],
    )

    assert result.action == "reuse_candidate"


def test_conflicting_candidate_snapshots_fail():
    existing = candidate()

    with pytest.raises(ValueError):
        plan_prefix_observation_assignment(
            observed(),
            [
                existing,
                replace(existing, address_space_id=uuid4()),
            ],
        )