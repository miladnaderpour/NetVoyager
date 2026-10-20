
"""Auditable decisions concerning physical-device discovery."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID


DeviceDiscoveryDecisionType: TypeAlias = Literal[
    "relationship_status",
    "candidate_resolution",
    "candidate_lifecycle",
    "candidate_attributes",
]

DeviceDiscoverySubjectType: TypeAlias = Literal[
    "candidate",
    "relationship",
]

DeviceDiscoveryActorType: TypeAlias = Literal[
    "human",
    "system",
    "ai_agent",
]


@dataclass(frozen=True, slots=True)
class DeviceDiscoveryDecision:
    """Describe an authorized change to device-discovery state.

    A decision records an action already authorized and performed by
    the calling application. It does not evaluate identity evidence,
    authorize an actor, or apply the state transition itself.

    The actor identifies who performed the action, including human
    engineers, automation services, and AI agents.

    Evidence IDs provide provenance references and are not used as
    relationship or candidate identity keys.
    """

    decision_type: DeviceDiscoveryDecisionType
    subject_id: UUID
    previous_value: str | None
    new_value: str
    evidence_ids: tuple[UUID, ...]
    reason: str | None
    timestamp: datetime
    source_id: str | None = None
    method: str | None = None
    policy_version: int | None = None

    # Required keyword-only audit context.
    subject_type: DeviceDiscoverySubjectType = field(kw_only=True)
    actor_type: DeviceDiscoveryActorType = field(kw_only=True)
    actor_id: str = field(kw_only=True)

    def __post_init__(self) -> None:
        """Validate required discovery decision audit metadata."""
        if self.subject_type not in {"candidate", "relationship"}:
            raise ValueError(
                f"Invalid discovery decision subject type: "
                f"{self.subject_type!r}"
            )

        if self.actor_type not in {"human", "system", "ai_agent"}:
            raise ValueError(
                f"Invalid discovery decision actor type: "
                f"{self.actor_type!r}"
            )

        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError(
                "Discovery decision actor_id must be a non-empty string."
            )

        if not isinstance(self.timestamp, datetime):
            raise ValueError(
                "Discovery decision timestamp must be a datetime."
            )

        if (
            self.timestamp.tzinfo is None
            or self.timestamp.utcoffset() is None
        ):
            raise ValueError(
                "Discovery decision timestamp must be timezone-aware."
            )
