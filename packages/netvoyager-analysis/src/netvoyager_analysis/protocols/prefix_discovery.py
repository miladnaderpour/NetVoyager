
"""Persistence-independent contracts for network-prefix discovery.

Repositories persist already-determined discovery state.
Matching, correlation, authorization, and promotion decisions
belong to application and analysis services.

Transaction ownership belongs to the Unit of Work.
"""

from typing import Protocol
from uuid import UUID

from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.decisions import (
    PrefixDiscoveryDecision,
)
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
)


class PrefixDiscoveryRepositoryProtocol(Protocol):
    """Provide durable access to prefix discovery state."""

    def add_observation(
        self,
        observation: PrefixObservation,
        dataset_id: UUID,
        *,
        source_name: str | None = None,
        source_method: str | None = None,
    ) -> None:
        """Persist an observation with its collection source context."""
        ...

    def get_observation(
        self,
        observation_id: UUID,
    ) -> PrefixObservation | None:
        """Return an observation by identity."""
        ...

    def get_observation_source(
        self,
        observation_id: UUID,
    ) -> tuple[str, str] | None:
        """Return the observation's registered policy source and method."""
        ...

    def get_candidate(
        self,
        candidate_id: UUID,
    ) -> PrefixDiscoveryCandidate | None:
        """Return a candidate by identity."""
        ...

    def find_candidates(
        self,
        prefix: str,
        address_space_id: UUID | None = None,
    ) -> tuple[PrefixDiscoveryCandidate, ...]:
        """Find candidates by normalized CIDR.

        A None address_space_id disables address-space filtering.
        It does not mean the global address space.
        """
        ...

    def add_candidate(
        self,
        candidate: PrefixDiscoveryCandidate,
    ) -> None:
        """Insert a new candidate."""
        ...

    def save_candidate(
        self,
        candidate: PrefixDiscoveryCandidate,
    ) -> None:
        """Persist an already-authorized candidate snapshot."""
        ...

    def link_observation(
        self,
        observation_id: UUID,
        candidate_id: UUID,
    ) -> None:
        """Associate an observation with a candidate idempotently."""
        ...

    def candidate_observation_ids(
        self,
        candidate_id: UUID,
    ) -> tuple[UUID, ...]:
        """Return observation identities associated with a candidate."""
        ...

    def get_relationship(
        self,
        relationship_id: UUID,
    ) -> PrefixDiscoveryCandidateRelationship | None:
        """Retrieve a candidate relationship."""
        ...

    def find_relationship(
        self,
        candidate_a_id: UUID,
        candidate_b_id: UUID,
    ) -> PrefixDiscoveryCandidateRelationship | None:
        """Find a relationship regardless of candidate ordering."""
        ...

    def relationships_for_candidate(
        self,
        candidate_id: UUID,
    ) -> tuple[PrefixDiscoveryCandidateRelationship, ...]:
        """Return relationships involving a candidate."""
        ...

    def add_relationship(
        self,
        relationship: PrefixDiscoveryCandidateRelationship,
    ) -> None:
        """Insert a new candidate relationship."""
        ...

    def save_relationship(
        self,
        relationship: PrefixDiscoveryCandidateRelationship,
    ) -> None:
        """Persist an authorized relationship-state change."""
        ...

    def candidates_for_prefix(
        self,
        prefix_id: UUID,
    ) -> tuple[PrefixDiscoveryCandidate, ...]:
        """Return candidates resolved to a canonical NetworkPrefix."""
        ...

    def append_decision(
        self,
        decision: PrefixDiscoveryDecision,
    ) -> None:
        """Append an immutable, previously authorized decision."""
        ...

    def decisions_for(
        self,
        subject_id: UUID,
    ) -> tuple[PrefixDiscoveryDecision, ...]:
        """Return discovery decisions for a candidate or relationship."""
        ...
