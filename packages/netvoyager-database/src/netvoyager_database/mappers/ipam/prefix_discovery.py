
"""Map prefix discovery domain models to SQL persistence entities."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import ip_network
from typing import cast
from uuid import UUID

from netvoyager_core.exceptions import NetVoyagerInvariantError

from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
    PrefixDiscoveryCandidateStatus,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
    PrefixDiscoveryRelationshipStatus,
)
from netvoyager_network.ipam.discovery.decisions import (
    PrefixDiscoveryDecision,
    PrefixDiscoveryDecisionType,
    PrefixDiscoverySubjectType,
    PrefixDiscoveryActorType,
)
from netvoyager_database.entities.ipam import (
    PrefixObservationEntity,
    PrefixDiscoveryCandidateEntity,
    PrefixDiscoveryRelationshipEntity,
    PrefixDiscoveryDecisionEntity,
)


def _utc(value: datetime) -> datetime:
    """Restore timezone stripped by SQLite or convert an aware value to UTC."""
    return (
        value.replace(tzinfo=UTC)
        if value.tzinfo is None
        else value.astimezone(UTC)
    )


def _enum(value: str, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise ValueError(f"Invalid persisted {label}: {value}")
    return value


def observation_to_entity(
    observation: PrefixObservation,
    dataset_id: UUID,
) -> PrefixObservationEntity:
    return PrefixObservationEntity(
        observation_id=observation.observation_id,
        dataset_id=dataset_id,
        local_ref=observation.local_ref,
        prefix=observation.prefix.with_prefixlen,
        observation_kind=observation.observation_kind,
        routing_context=observation.routing_context,
        address_space_id=observation.address_space_id,
        local_device_ref=observation.local_device_ref,
    )


def observation_to_domain(
    entity: PrefixObservationEntity,
) -> PrefixObservation:
    return PrefixObservation(
        observation_id=entity.observation_id,
        local_ref=entity.local_ref,
        prefix=ip_network(entity.prefix),
        observation_kind=entity.observation_kind,
        routing_context=entity.routing_context,
        address_space_id=entity.address_space_id,
        local_device_ref=entity.local_device_ref,
    )


def candidate_to_entity(
    candidate: PrefixDiscoveryCandidate,
) -> PrefixDiscoveryCandidateEntity:
    return PrefixDiscoveryCandidateEntity(
        candidate_id=candidate.candidate_id,
        status=candidate.status,
        prefix=(
            candidate.prefix.with_prefixlen
            if candidate.prefix is not None
            else None
        ),
        address_space_id=candidate.address_space_id,
        first_seen=_utc(candidate.first_seen),
        last_seen=_utc(candidate.last_seen),
        resolved_prefix_id=candidate.resolved_prefix_id,
    )


def candidate_to_domain(
    entity: PrefixDiscoveryCandidateEntity,
) -> PrefixDiscoveryCandidate:
    status = cast(
        PrefixDiscoveryCandidateStatus,
        _enum(
            entity.status,
            {
                "candidate",
                "corroborated",
                "resolved",
                "rejected",
                "retired",
            },
            "candidate status",
        ),
    )

    return PrefixDiscoveryCandidate(
        candidate_id=entity.candidate_id,
        status=status,
        prefix=(
            ip_network(entity.prefix)
            if entity.prefix is not None
            else None
        ),
        address_space_id=entity.address_space_id,
        first_seen=_utc(entity.first_seen),
        last_seen=_utc(entity.last_seen),
        resolved_prefix_id=entity.resolved_prefix_id,
    )


def relationship_to_entity(
    relationship: PrefixDiscoveryCandidateRelationship,
) -> PrefixDiscoveryRelationshipEntity:
    return PrefixDiscoveryRelationshipEntity(
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
    entity: PrefixDiscoveryRelationshipEntity,
) -> PrefixDiscoveryCandidateRelationship:
    status = cast(
        PrefixDiscoveryRelationshipStatus,
        _enum(
            entity.status,
            {"possible", "confirmed", "rejected"},
            "relationship status",
        ),
    )

    relationship = PrefixDiscoveryCandidateRelationship(
        candidate_a_id=entity.candidate_a_id,
        candidate_b_id=entity.candidate_b_id,
        status=status,
        evidence_ids=frozenset(
            UUID(evidence_id)
            for evidence_id in entity.evidence_ids
        ),
    )

    if relationship.relationship_id != entity.relationship_id:
        raise NetVoyagerInvariantError(
            code="database.prefix_relationship_identity_mismatch",
            message=(
                "Stored prefix relationship identity differs "
                "from domain identity."
            ),
        )

    return relationship


def decision_to_entity(
    decision: PrefixDiscoveryDecision,
) -> PrefixDiscoveryDecisionEntity:
    return PrefixDiscoveryDecisionEntity(
        decision_type=decision.decision_type,
        subject_type=decision.subject_type,
        subject_id=decision.subject_id,
        actor_type=decision.actor_type,
        actor_id=decision.actor_id,
        previous_value=decision.previous_value,
        new_value=decision.new_value,
        evidence_ids=[
            str(evidence_id)
            for evidence_id in decision.evidence_ids
        ],
        reason=decision.reason,
        timestamp=_utc(decision.timestamp),
        source_id=decision.source_id,
        method=decision.method,
        policy_version=decision.policy_version,
    )


def decision_to_domain(
    entity: PrefixDiscoveryDecisionEntity,
) -> PrefixDiscoveryDecision:
    return PrefixDiscoveryDecision(
        decision_type=cast(
            PrefixDiscoveryDecisionType,
            _enum(
                entity.decision_type,
                {
                    "relationship_status",
                    "candidate_resolution",
                    "candidate_lifecycle",
                    "candidate_attributes",
                },
                "decision type",
            ),
        ),
        subject_type=cast(
            PrefixDiscoverySubjectType,
            _enum(
                entity.subject_type,
                {"candidate", "relationship"},
                "subject type",
            ),
        ),
        subject_id=entity.subject_id,
        actor_type=cast(
            PrefixDiscoveryActorType,
            _enum(
                entity.actor_type,
                {"human", "system", "ai_agent"},
                "actor type",
            ),
        ),
        actor_id=entity.actor_id,
        previous_value=entity.previous_value,
        new_value=entity.new_value,
        evidence_ids=tuple(
            UUID(evidence_id)
            for evidence_id in entity.evidence_ids
        ),
        reason=entity.reason,
        timestamp=_utc(entity.timestamp),
        source_id=entity.source_id,
        method=entity.method,
        policy_version=entity.policy_version,
    )
