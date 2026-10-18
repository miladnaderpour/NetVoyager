
"""Map discovery relationships between domain and SQLAlchemy entities."""

from __future__ import annotations

from typing import cast

from netvoyager_core.exceptions import NetVoyagerInvariantError
from netvoyager_network.device.discovery.relationships import (
    DeviceDiscoveryCandidateRelationship,
    DeviceDiscoveryRelationshipStatus,
)

from netvoyager_database.entities.devices.discovery_relationship import (
    DeviceDiscoveryRelationshipEntity,
)


def _relationship_status(value: str) -> DeviceDiscoveryRelationshipStatus:
    """Validate and narrow a stored relationship status."""
    if value not in {"possible", "confirmed", "rejected"}:
        raise ValueError(f"Invalid stored relationship status: {value}")

    return cast(DeviceDiscoveryRelationshipStatus, value)


def relationship_to_entity(
    relationship: DeviceDiscoveryCandidateRelationship,
) -> DeviceDiscoveryRelationshipEntity:
    """Convert a relationship snapshot into a persistence entity."""
    return DeviceDiscoveryRelationshipEntity(
        relationship_id=relationship.relationship_id,
        candidate_a_id=relationship.candidate_a_id,
        candidate_b_id=relationship.candidate_b_id,
        status=relationship.status,
        evidence_ids=[
            str(evidence_id)
            for evidence_id in sorted(relationship.evidence_ids)
        ],
    )


def relationship_to_domain(
    entity: DeviceDiscoveryRelationshipEntity,
) -> DeviceDiscoveryCandidateRelationship:
    """Reconstruct and verify a persisted discovery relationship."""
    from uuid import UUID

    relationship = DeviceDiscoveryCandidateRelationship(
        candidate_a_id=entity.candidate_a_id,
        candidate_b_id=entity.candidate_b_id,
        status=_relationship_status(entity.status),
        evidence_ids=frozenset(
            UUID(evidence_id)
            for evidence_id in entity.evidence_ids
        ),
    )

    if relationship.relationship_id != entity.relationship_id:
        raise NetVoyagerInvariantError(
            code="database.discovery_relationship_identity_mismatch",
            message="Stored discovery relationship identity is invalid.",
            details={
                "stored_relationship_id": str(entity.relationship_id),
                "expected_relationship_id": str(
                    relationship.relationship_id
                ),
            },
        )

    return relationship
