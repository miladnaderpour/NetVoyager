"""Provisional physical-device identities used during discovery.

Discovery candidates are immutable snapshots. The discovery store controls
state changes and keeps resolution and lifecycle history separately.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Literal, TypeAlias
from uuid import UUID, uuid4


DeviceDiscoveryCandidateStatus: TypeAlias = Literal[
    "candidate", "corroborated", "resolved", "rejected", "retired",
]


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DeviceDiscoveryCandidate:
    """One provisional physical-device identity, independent of its attributes.

    Summary attributes may change through a store operation; historical
    source observations remain in EvidenceStore. A resolved candidate keeps
    its own ID and is not automatically consolidated with other candidates.
    """

    candidate_id: UUID = field(default_factory=uuid4, kw_only=True)
    status: DeviceDiscoveryCandidateStatus = "candidate"
    name: str | None = None
    host_name: str | None = None
    serial_number: str | None = None
    management_ip: IPv4Address | None = None
    first_seen: datetime = field(default_factory=_utc_now, kw_only=True)
    last_seen: datetime = field(default_factory=_utc_now, kw_only=True)
    resolved_device_id: UUID | None = None

    def __post_init__(self) -> None:
        """Ensure resolution and lifecycle fields agree."""
        if self.status not in {
            "candidate", "corroborated", "resolved", "rejected", "retired",
        }:
            raise ValueError(f"Invalid candidate status: {self.status}")
        if (self.status == "resolved") != (self.resolved_device_id is not None):
            raise ValueError("Resolved status requires exactly one resolved device ID")
        if self.first_seen.tzinfo is None or self.last_seen.tzinfo is None:
            raise ValueError("Candidate timestamps must be timezone aware")
        if self.last_seen < self.first_seen:
            raise ValueError("last_seen cannot precede first_seen")
