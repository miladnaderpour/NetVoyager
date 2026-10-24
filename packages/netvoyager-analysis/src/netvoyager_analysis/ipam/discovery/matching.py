"""Pure prefix observation-to-candidate identity comparison."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)

PrefixMatchStrength = Literal["exact", "possible"]


@dataclass(frozen=True, slots=True)
class PrefixCandidateMatch:
    """An identity match signal, not a reconciliation decision."""

    observation_id: UUID
    candidate_id: UUID
    strength: PrefixMatchStrength
    reason: str


def compare_prefix_observation(
    observation: PrefixObservation,
    candidate: PrefixDiscoveryCandidate,
) -> PrefixCandidateMatch | None:
    """Compare CIDR identity within an explicitly known AddressSpace.

    Equal CIDRs alone cannot establish identity when either AddressSpace
    is unknown. Unknown is never interpreted as global.

    Rejected and retired candidates are excluded.
    """
    if candidate.status in {"rejected", "retired"}:
        return None

    if candidate.prefix is None or observation.prefix != candidate.prefix:
        return None

    observed_space = observation.address_space_id
    candidate_space = candidate.address_space_id

    if observed_space is None or candidate_space is None:
        return None

    if observed_space != candidate_space:
        return None

    return PrefixCandidateMatch(
        observation_id=observation.observation_id,
        candidate_id=candidate.candidate_id,
        strength="exact",
        reason=(
            "Equal CIDR within the same explicitly identified "
            "AddressSpace"
        ),
    )