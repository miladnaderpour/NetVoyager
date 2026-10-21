
"""Auditable decisions concerning prefix discovery."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID


PrefixDiscoveryDecisionType: TypeAlias = Literal[
    "relationship_status",
    "candidate_resolution",
    "candidate_lifecycle",
    "candidate_attributes",
]

PrefixDiscoverySubjectType: TypeAlias = Literal[
    "candidate",
    "relationship",
]

PrefixDiscoveryActorType: TypeAlias = Literal[
    "human",
    "system",
    "ai_agent",
]


@dataclass(frozen=True, slots=True)
class PrefixDiscoveryDecision:
    """Audit an already authorized action; does not authorize or apply it."""

    decision_type: PrefixDiscoveryDecisionType
    subject_id: UUID
    previous_value: str | None
    new_value: str
    evidence_ids: tuple[UUID, ...]
    reason: str | None
    timestamp: datetime
    source_id: str | None = None
    method: str | None = None
    policy_version: int | None = None

    subject_type: PrefixDiscoverySubjectType = field(kw_only=True)
    actor_type: PrefixDiscoveryActorType = field(kw_only=True)
    actor_id: str = field(kw_only=True)

    def __post_init__(self) -> None:
        """Validate mandatory audit context."""
        if self.decision_type not in {
            "relationship_status",
            "candidate_resolution",
            "candidate_lifecycle",
            "candidate_attributes",
        }:
            raise ValueError(
                f"Invalid discovery decision type: {self.decision_type}"
            )

        if self.subject_type not in {"candidate", "relationship"}:
            raise ValueError(
                f"Invalid discovery subject type: {self.subject_type}"
            )

        if self.actor_type not in {"human", "system", "ai_agent"}:
            raise ValueError(
                f"Invalid discovery actor type: {self.actor_type}"
            )

        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError(
                "Discovery decision actor_id must be nonempty"
            )

        if not isinstance(self.timestamp, datetime) or (
            self.timestamp.tzinfo is None
            or self.timestamp.utcoffset() is None
        ):
            raise ValueError(
                "Discovery decision timestamp must be timezone aware"
            )
