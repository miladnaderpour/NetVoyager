
"""Non-destructive identity hypotheses between prefix candidates."""

from dataclasses import dataclass, field
from typing import Literal, TypeAlias
from uuid import UUID, uuid5


PrefixDiscoveryRelationshipStatus: TypeAlias = Literal[
    "possible",
    "confirmed",
    "rejected",
]

PREFIX_DISCOVERY_RELATIONSHIP_NAMESPACE = UUID(
    "8b2087f6-55cb-42d0-88b5-83e4ba291cc0"
)


@dataclass(frozen=True, slots=True)
class PrefixDiscoveryCandidateRelationship:
    """Symmetric candidate hypothesis; confirmation never promotes a prefix."""

    candidate_a_id: UUID
    candidate_b_id: UUID
    status: PrefixDiscoveryRelationshipStatus = "possible"
    evidence_ids: frozenset[UUID] = field(
        default_factory=frozenset, repr=False
    )
    relationship_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        """Canonicalize pair ordering and compute stable relationship identity."""
        if not isinstance(self.candidate_a_id, UUID) or not isinstance(
            self.candidate_b_id, UUID
        ):
            raise TypeError("Candidate references must be UUIDs")

        if self.candidate_a_id == self.candidate_b_id:
            raise ValueError("A candidate cannot relate to itself")

        if self.status not in {"possible", "confirmed", "rejected"}:
            raise ValueError(f"Invalid relationship status: {self.status}")

        first, second = sorted(
            (self.candidate_a_id, self.candidate_b_id)
        )

        object.__setattr__(self, "candidate_a_id", first)
        object.__setattr__(self, "candidate_b_id", second)
        object.__setattr__(
            self, "evidence_ids", frozenset(self.evidence_ids)
        )
        object.__setattr__(
            self,
            "relationship_id",
            uuid5(
                PREFIX_DISCOVERY_RELATIONSHIP_NAMESPACE,
                f"prefix-discovery-relationship:{first}:{second}",
            ),
        )
