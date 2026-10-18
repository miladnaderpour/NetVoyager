
"""Storage-independent repository contract for device discovery."""

from ipaddress import IPv4Address
from typing import Protocol
from uuid import UUID

from netvoyager_network.device.discovery.decisions import (
    DeviceDiscoveryDecision,
)
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.discovery.relationships import (
    DeviceDiscoveryCandidateRelationship,
)


class DeviceDiscoveryRepositoryProtocol(Protocol):
    """Provide persistence and queries for device discovery records.

    Repositories manage candidates, their relationships, resolutions,
    and decision history without evaluating physical identity or
    authorizing lifecycle transitions.

    Identity validation, reconciliation, and policy evaluation belong
    to the analysis layer.
    """

    def get_candidate(
        self,
        candidate_id: UUID,
    ) -> DeviceDiscoveryCandidate | None:
        """Return a candidate by its ID, if present."""
        ...

    def find_by_serial(
        self,
        serial_number: str,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return candidates with the exact stored serial number."""
        ...

    def find_by_management_ip(
        self,
        management_ip: IPv4Address,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return candidates with the given management IPv4 address."""
        ...

    def find_by_name(
        self,
        name: str,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return candidates with the given observed name."""
        ...

    def add_candidate(
        self,
        candidate: DeviceDiscoveryCandidate,
    ) -> None:
        """Persist a new candidate without replacing an existing one."""
        ...

    def save_candidate(
        self,
        candidate: DeviceDiscoveryCandidate,
    ) -> None:
        """Persist an existing candidate snapshot."""
        ...

    def get_relationship(
        self,
        relationship_id: UUID,
    ) -> DeviceDiscoveryCandidateRelationship | None:
        """Return a relationship by its ID, if present."""
        ...

    def find_relationship(
        self,
        candidate_a_id: UUID,
        candidate_b_id: UUID,
    ) -> DeviceDiscoveryCandidateRelationship | None:
        """Find a relationship independent of candidate order."""
        ...

    def relationships_for_candidate(
        self,
        candidate_id: UUID,
    ) -> tuple[DeviceDiscoveryCandidateRelationship, ...]:
        """Return relationships involving the given candidate."""
        ...

    def add_relationship(
        self,
        relationship: DeviceDiscoveryCandidateRelationship,
    ) -> None:
        """Persist a new candidate relationship."""
        ...

    def save_relationship(
        self,
        relationship: DeviceDiscoveryCandidateRelationship,
    ) -> None:
        """Persist an existing relationship snapshot."""
        ...

    def candidates_for_device(
        self,
        device_id: UUID,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return candidates currently resolved to a canonical device."""
        ...

    def save_resolution(
        self,
        candidate: DeviceDiscoveryCandidate,
    ) -> None:
        """Persist a candidate's already-decided resolution state.

        The calling service is responsible for validating and
        authorizing the resolution or reversal.
        """
        ...

    def decisions_for(
        self,
        subject_id: UUID,
    ) -> tuple[DeviceDiscoveryDecision, ...]:
        """Return recorded decisions for a candidate or relationship."""
        ...

    def append_decision(
        self,
        decision: DeviceDiscoveryDecision,
    ) -> None:
        """Append an immutable discovery decision record."""
        ...
