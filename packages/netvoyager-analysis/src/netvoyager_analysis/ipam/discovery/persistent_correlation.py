
"""Persist candidate correlation proposals in the caller's Unit of Work."""

from __future__ import annotations

from ipaddress import ip_network

from netvoyager_analysis.ipam.discovery.correlation import (
    PrefixCorrelationResult,
    correlate_prefix_candidates,
)
from netvoyager_analysis.protocols.unit_of_work import (
    UnitOfWorkProtocol,
)


class PrefixCandidateCorrelationService:
    """Correlate one CIDR's existing candidates without owning commits."""

    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    def correlate(self, prefix: str) -> PrefixCorrelationResult:
        """Persist only new possible relationships for a normalized CIDR."""
        normalized = ip_network(
            prefix,
            strict=False,
        ).with_prefixlen

        repository = self._uow.prefix_discovery

        candidates = repository.find_candidates(normalized)

        # Deduplicate symmetric relationships returned for both endpoints.
        existing = {}

        for candidate in candidates:
            for relationship in repository.relationships_for_candidate(
                candidate.candidate_id
            ):
                existing[relationship.relationship_id] = relationship

        result = correlate_prefix_candidates(
            candidates,
            existing.values(),
        )

        for relationship in result.proposed:
            repository.add_relationship(relationship)

        return result
