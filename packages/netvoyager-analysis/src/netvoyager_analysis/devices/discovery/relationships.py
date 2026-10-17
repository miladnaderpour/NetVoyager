"""Immutable identity hypotheses between two discovery candidates."""

from dataclasses import dataclass, field
from typing import Literal, TypeAlias
from uuid import UUID, uuid5


DeviceDiscoveryRelationshipStatus: TypeAlias = Literal[
    "possible", "confirmed", "rejected",
]

DEVICE_DISCOVERY_RELATIONSHIP_NAMESPACE = UUID(
    "7c4e8c49-2ec1-4d82-9e70-5e0a1f9d683b"
)


@dataclass(frozen=True, slots=True)
class DeviceDiscoveryCandidateRelationship:
    """A non-destructive, symmetric candidate identity hypothesis.

    Status and evidence are snapshots. The store records each transition;
    confirming a relationship never promotes a candidate automatically.
    """

    candidate_a_id: UUID
    candidate_b_id: UUID
    status: DeviceDiscoveryRelationshipStatus = "possible"
    evidence_ids: frozenset[UUID] = field(default_factory=frozenset, repr=False)
    relationship_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        """Derive the same stable relationship ID for either input order."""
        if self.candidate_a_id == self.candidate_b_id:
            raise ValueError("A candidate cannot relate to itself")
        if self.status not in {"possible", "confirmed", "rejected"}:
            raise ValueError(f"Invalid relationship status: {self.status}")

        first, second = sorted((self.candidate_a_id, self.candidate_b_id))
        object.__setattr__(self, "candidate_a_id", first)
        object.__setattr__(self, "candidate_b_id", second)
        object.__setattr__(self, "evidence_ids", frozenset(self.evidence_ids))
        object.__setattr__(
            self,
            "relationship_id",
            uuid5(
                DEVICE_DISCOVERY_RELATIONSHIP_NAMESPACE,
                f"device-discovery-relationship:{first}:{second}",
            ),
        )
