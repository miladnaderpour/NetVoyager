
"""Map discovery decisions between domain and SQLAlchemy entities."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from netvoyager_network.device.discovery.decisions import (
    DeviceDiscoveryActorType,
    DeviceDiscoveryDecision,
    DeviceDiscoveryDecisionType,
    DeviceDiscoverySubjectType,
)

from netvoyager_database.entities.devices.discovery_decision import (
    DeviceDiscoveryDecisionEntity,
)


def _as_utc(value: datetime) -> datetime:
    """Normalize a timestamp or restore SQLite-stored UTC timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _decision_type(value: str) -> DeviceDiscoveryDecisionType:
    """Validate a persisted decision classification."""
    valid = {
        "relationship_status",
        "candidate_resolution",
        "candidate_lifecycle",
        "candidate_attributes",
    }

    if value not in valid:
        raise ValueError(f"Invalid stored decision type: {value}")

    return cast(DeviceDiscoveryDecisionType, value)


def _subject_type(value: str) -> DeviceDiscoverySubjectType:
    """Validate the persisted subject classification."""
    if value not in {"candidate", "relationship"}:
        raise ValueError(f"Invalid stored subject type: {value}")

    return cast(DeviceDiscoverySubjectType, value)


def _actor_type(value: str) -> DeviceDiscoveryActorType:
    """Validate the persisted actor classification."""
    if value not in {"human", "system", "ai_agent"}:
        raise ValueError(f"Invalid stored actor type: {value}")

    return cast(DeviceDiscoveryActorType, value)


def decision_to_entity(
    decision: DeviceDiscoveryDecision,
) -> DeviceDiscoveryDecisionEntity:
    """Convert an approved discovery decision into an audit entity."""
    return DeviceDiscoveryDecisionEntity(
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
        timestamp=_as_utc(decision.timestamp),
        source_id=decision.source_id,
        method=decision.method,
        policy_version=decision.policy_version,
    )


def decision_to_domain(
    entity: DeviceDiscoveryDecisionEntity,
) -> DeviceDiscoveryDecision:
    """Reconstruct a discovery decision from its stored audit row."""
    return DeviceDiscoveryDecision(
        decision_type=_decision_type(entity.decision_type),
        subject_id=entity.subject_id,
        previous_value=entity.previous_value,
        new_value=entity.new_value,
        evidence_ids=tuple(
            UUID(evidence_id) for evidence_id in entity.evidence_ids
        ),
        reason=entity.reason,
        timestamp=_as_utc(entity.timestamp),
        source_id=entity.source_id,
        method=entity.method,
        policy_version=entity.policy_version,
        subject_type=_subject_type(entity.subject_type),
        actor_type=_actor_type(entity.actor_type),
        actor_id=entity.actor_id,
    )
