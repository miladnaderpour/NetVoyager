
"""Auditable decisions concerning physical-device discovery."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID


DeviceDiscoveryDecisionType: TypeAlias = Literal[
    "relationship_status", "candidate_resolution", "candidate_lifecycle",
    "candidate_attributes",
]


@dataclass(frozen=True, slots=True)
class DeviceDiscoveryDecision:
    """An append-only description of an approved discovery change.

    Evidence IDs are references, never the source of matching attributes.
    The calling reconciliation layer is responsible for validating evidence
    and policy authorization; repositories do not certify either.
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
