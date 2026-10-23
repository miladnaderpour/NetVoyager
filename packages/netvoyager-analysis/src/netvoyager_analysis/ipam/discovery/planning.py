
"""Plan prefix observation assignment without changing discovery state."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from netvoyager_analysis.ipam.discovery.matching import (
    PrefixCandidateMatch,
    compare_prefix_observation,
)
from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)


PrefixAssignmentAction = Literal[
    "reuse_candidate",
    "create_candidate",
]


@dataclass(frozen=True, slots=True)
class PrefixObservationAssignmentPlan:
    """Proposed observation assignment, not an applied persistence operation."""

    observation_id: UUID
    action: PrefixAssignmentAction
    candidate: PrefixDiscoveryCandidate
    possible_matches: tuple[PrefixCandidateMatch, ...] = ()


def plan_prefix_observation_assignment(
    observation: PrefixObservation,
    candidates: Iterable[PrefixDiscoveryCandidate],
) -> PrefixObservationAssignmentPlan:
    """Reuse one exact candidate or create a distinct provisional candidate.

    Ambiguous exact matches are not resolved by arbitrary ordering.
    A new candidate is proposed instead; all matches remain review signals.
    """
    unique: dict[UUID, PrefixDiscoveryCandidate] = {}

    for candidate in candidates:
        previous = unique.get(candidate.candidate_id)
        if previous is not None and previous != candidate:
            raise ValueError(
                "Conflicting snapshots for the same candidate ID"
            )
        unique[candidate.candidate_id] = candidate

    matches = [
        match
        for candidate in unique.values()
        if (
            match := compare_prefix_observation(
                observation,
                candidate,
            )
        ) is not None
    ]

    exact = [
        match
        for match in matches
        if match.strength == "exact"
    ]

    if len(exact) == 1:
        return PrefixObservationAssignmentPlan(
            observation_id=observation.observation_id,
            action="reuse_candidate",
            candidate=unique[exact[0].candidate_id],
        )

    proposed = PrefixDiscoveryCandidate(
        prefix=observation.prefix,
        address_space_id=observation.address_space_id,
    )

    return PrefixObservationAssignmentPlan(
        observation_id=observation.observation_id,
        action="create_candidate",
        candidate=proposed,
        possible_matches=tuple(
            sorted(matches, key=lambda match: match.candidate_id)
        ),
    )
