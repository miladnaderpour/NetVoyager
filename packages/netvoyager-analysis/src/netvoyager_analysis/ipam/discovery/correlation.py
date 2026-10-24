
"""Pure, non-destructive correlation of prefix discovery candidates.

Only candidates with the same normalized CIDR are compared. Correlation
proposes relationships; it never changes identities or lifecycle states.
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
    """Propose compatible candidate relationships, grouped by exact CIDR.

    Different known address spaces never correlate. Missing address-space
    information may yield a possible relationship. Existing relationships,
    including rejected relationships, always suppress a new proposal.
    """
    unique: dict[UUID, PrefixDiscoveryCandidate] = {}

    for candidate in candidates:
        previous = unique.get(candidate.candidate_id)

        if previous is not None and previous != candidate:
            raise ValueError(
                "Conflicting snapshots for the same candidate ID"
            )

        unique[candidate.candidate_id] = candidate

    by_prefix: dict[str, list[PrefixDiscoveryCandidate]] = {}

    for candidate in unique.values():
        if (
            candidate.status in {"rejected", "retired"}
            or candidate.prefix is None
        ):
            continue

        by_prefix.setdefault(
            candidate.prefix.with_prefixlen,
            [],
        ).append(candidate)

    known_relationships = {
        relationship.relationship_id
        for relationship in existing_relationships
    }

    proposed: list[PrefixDiscoveryCandidateRelationship] = []

    for prefix in sorted(by_prefix):
        group = sorted(
            by_prefix[prefix],
            key=lambda item: item.candidate_id,
        )

        for index, left in enumerate(group):
            for right in group[index + 1:]:
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

    # Preserve the former global candidate-ID ordering across CIDR groups.
    proposed.sort(
        key=lambda item: (
            item.candidate_a_id,
            item.candidate_b_id,
        )
    )

    return PrefixCorrelationResult(
        proposed=tuple(proposed),
    )
