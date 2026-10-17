
"""Models for evidence-backed device attribute assertions.

Attribute assertions represent proposed or validated values associated
with discovery candidates or canonical network devices.

Evidence records, findings, policy evaluation, and reconciliation
decisions remain separate from the assertion models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv4Network
from typing import Literal, TypeAlias
from uuid import UUID, uuid4


AttributeTargetType: TypeAlias = Literal[
    "device_discovery_candidate",
    "network_device",
]

AttributeAssertionStatus: TypeAlias = Literal[
    "proposed",
    "confirmed",
    "disputed",
    "superseded",
]

AttributeValue: TypeAlias = str | int | bool | IPv4Address | IPv4Network


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class AttributeAssertion:
    """Represent one claimed attribute value for one network object.

    Assertion identity is independent of the observed attribute value
    and the target's canonical identity.

    Supporting evidence remains in EvidenceStore. Multiple observations
    may support the same assertion without creating duplicate assertions.

    Status changes must be performed through AttributeAssertionStore.
    """

    target_type: AttributeTargetType
    target_id: UUID
    field_name: str
    value: AttributeValue

    evidence_ids: tuple[UUID, ...]

    status: AttributeAssertionStatus = "proposed"

    assertion_id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
    )

    created_at: datetime = field(
        default_factory=_utc_now,
        kw_only=True,
    )

    def __post_init__(self) -> None:
        """Validate assertion identity, value, and evidence references."""
        if self.target_type not in {
            "device_discovery_candidate",
            "network_device",
        }:
            raise ValueError(
                f"Invalid assertion target type: {self.target_type}"
            )

        if not self.field_name.strip():
            raise ValueError("Attribute name cannot be empty")

        if not isinstance(
            self.value,
            (str, int, bool, IPv4Address),
        ):
            raise ValueError(
                "Unsupported attribute assertion value"
            )

        if self.status not in {
            "proposed",
            "confirmed",
            "disputed",
            "superseded",
        }:
            raise ValueError(
                f"Invalid attribute assertion status: {self.status}"
            )

        if not self.evidence_ids:
            raise ValueError(
                "Attribute assertions require supporting evidence"
            )

        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError(
                "Duplicate assertion evidence IDs are not allowed"
            )


@dataclass(frozen=True, slots=True)
class AttributeAssertionDecision:
    """Record a change to an attribute assertion.

    Decisions preserve previous and new validation states, supporting
    evidence, and the policy used to authorize the transition.

    A decision does not replace the original evidence records.
    """

    assertion_id: UUID

    previous_status: AttributeAssertionStatus
    new_status: AttributeAssertionStatus

    evidence_ids: tuple[UUID, ...]

    source_id: str
    method: str
    policy_version: int

    reason: str | None = None

    decision_id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
    )

    timestamp: datetime = field(
        default_factory=_utc_now,
        kw_only=True,
    )
