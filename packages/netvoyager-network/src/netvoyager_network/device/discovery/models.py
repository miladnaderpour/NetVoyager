
"""Provisional physical-device identities used during discovery.

Discovery candidates are immutable snapshots. The reconciliation layer
controls state changes and keeps resolution and lifecycle history separately.

Candidate attributes represent reported information, not independently
authorized canonical device facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Literal, TypeAlias
from uuid import UUID, uuid4


DeviceDiscoveryCandidateStatus: TypeAlias = Literal[
    "candidate",
    "corroborated",
    "resolved",
    "rejected",
    "retired",
]


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DeviceDiscoveryCandidate:
    """One provisional physical-device identity.

    Candidate identity is independent of reported attributes.

    Summary attributes may change through governed reconciliation;
    original source information and decisions remain separate.

    Several candidates may resolve to the same canonical NetworkDevice
    without merging their independent candidate identities.

    A reported site is not a confirmed canonical site association.
    """

    # Independent discovery identity
    candidate_id: UUID = field(default_factory=uuid4, kw_only=True)

    # Discovery lifecycle
    status: DeviceDiscoveryCandidateStatus = "candidate"

    # Device identifiers
    name: str | None = None
    host_name: str | None = None
    serial_number: str | None = None
    management_ip: IPv4Address | None = None

    # Reported inventory attributes
    site: str | None = None
    role: str | None = None
    primary_ipv4: IPv4Address | None = None

    manufacturer: str | None = None
    model: str | None = None
    software_version: str | None = None
    asset_tag: str | None = None

    # Discovery timestamps
    first_seen: datetime = field(
        default_factory=_utc_now,
        kw_only=True,
    )
    last_seen: datetime = field(
        default_factory=_utc_now,
        kw_only=True,
    )

    # Authorized canonical resolution
    resolved_device_id: UUID | None = None

    def __post_init__(self) -> None:
        """Validate discovery lifecycle and temporal consistency."""
        if self.status not in {
            "candidate",
            "corroborated",
            "resolved",
            "rejected",
            "retired",
        }:
            raise ValueError(
                f"Invalid candidate status: {self.status}"
            )

        if (
            self.status == "resolved"
        ) != (
            self.resolved_device_id is not None
        ):
            raise ValueError(
                "Resolved status requires exactly one resolved device ID"
            )

        if (
            self.first_seen.tzinfo is None
            or self.last_seen.tzinfo is None
        ):
            raise ValueError(
                "Candidate timestamps must be timezone aware"
            )

        if self.last_seen < self.first_seen:
            raise ValueError(
                "last_seen cannot precede first_seen"
            )
