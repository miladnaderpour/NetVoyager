
"""Pure, non-destructive correlation of prefix discovery candidates.

Correlation only proposes possible identity relationships.
It never confirms, rejects, merges, resolves, or promotes candidates.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
)


@dataclass(frozen=True, slots=True)
class PrefixCorrelationResult:
    """New relationship proposals; existing relationships remain untouched."""

    proposed: tuple[PrefixDiscoveryCandidateRelationship, ...]


def correlate_prefix_candidates(
    candidates: Iterable[PrefixDiscoveryCandidate],
    existing_relationships: Iterable[
        PrefixDiscoveryCandidateRelationship
    ] = (),
) -> PrefixCorrelationResult:
    """Propose possible relationships between compatible prefix candidates.

    Rules:
    - Different CIDRs do not establish identity.
    - Different known address spaces are incompatible.
    - Equal CIDRs with unresolved space may be correlated provisionally.
    - Existing relationships, including rejected ones, are authoritative
      for this planning operation and are never overwritten.
    - No candidate or relationship state is mutated.
    """
    unique: dict[UUID, PrefixDiscoveryCandidate] = {}

    for candidate in candidates:
        existing = unique.get(candidate.candidate_id)
        if existing is not None and existing != candidate:
            raise ValueError(
                "Conflicting snapshots for the same candidate ID"
            )
        unique[candidate.candidate_id] = candidate

    eligible = sorted(
        (
            candidate
            for candidate in unique.values()
            if candidate.status not in {"rejected", "retired"}
            and candidate.prefix is not None
        ),
        key=lambda candidate: candidate.candidate_id,
    )

    known_relationships = {
        relationship.relationship_id
        for relationship in existing_relationships
    }

    proposed: list[PrefixDiscoveryCandidateRelationship] = []

    for index, left in enumerate(eligible):
        for right in eligible[index + 1:]:
            if left.prefix != right.prefix:
                continue

            if (
                left.address_space_id is not None
                and right.address_space_id is not None
                and left.address_space_id != right.address_space_id
            ):
                continue

            relationship = PrefixDiscoveryCandidateRelationship(
                candidate_a_id=left.candidate_id,
                candidate_b_id=right.candidate_id,
                status="possible",
            )

            if relationship.relationship_id in known_relationships:
                continue

            known_relationships.add(relationship.relationship_id)
            proposed.append(relationship)

    return PrefixCorrelationResult(proposed=tuple(proposed))
