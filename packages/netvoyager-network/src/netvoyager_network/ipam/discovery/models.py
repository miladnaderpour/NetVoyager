
"""Immutable provisional prefix identities used during discovery."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import IPv4Network, IPv6Network
from typing import Literal, TypeAlias
from uuid import UUID, uuid4


PrefixDiscoveryCandidateStatus: TypeAlias = Literal[
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
class PrefixDiscoveryCandidate:
    """Provisional prefix identity independent of CIDR or address space.

    Candidate snapshots are immutable. Reconciliation owns transitions;
    source observations and authorization history remain separate.
    """

    candidate_id: UUID = field(default_factory=uuid4, kw_only=True)
    status: PrefixDiscoveryCandidateStatus = "candidate"
    prefix: IPv4Network | IPv6Network | None = None
    address_space_id: UUID | None = None
    first_seen: datetime = field(default_factory=_utc_now, kw_only=True)
    last_seen: datetime = field(default_factory=_utc_now, kw_only=True)
    resolved_prefix_id: UUID | None = None

    def __post_init__(self) -> None:
        """Validate lifecycle, optional identity hints and timestamps."""
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")

        if self.status not in {
            "candidate", "corroborated", "resolved", "rejected", "retired",
        }:
            raise ValueError(f"Invalid candidate status: {self.status}")

        if self.prefix is not None and not isinstance(
            self.prefix, (IPv4Network, IPv6Network)
        ):
            raise TypeError(
                "prefix must be an IPv4Network, IPv6Network or None"
            )

        if self.address_space_id is not None and not isinstance(
            self.address_space_id, UUID
        ):
            raise TypeError("address_space_id must be a UUID or None")

        if self.resolved_prefix_id is not None and not isinstance(
            self.resolved_prefix_id, UUID
        ):
            raise TypeError("resolved_prefix_id must be a UUID or None")

        if (self.status == "resolved") != (
            self.resolved_prefix_id is not None
        ):
            raise ValueError(
                "Resolved status requires exactly one resolved prefix ID"
            )

        if not isinstance(self.first_seen, datetime) or not isinstance(
            self.last_seen, datetime
        ):
            raise TypeError("Candidate timestamps must be datetime values")

        if (
            self.first_seen.tzinfo is None
            or self.first_seen.utcoffset() is None
            or self.last_seen.tzinfo is None
            or self.last_seen.utcoffset() is None
        ):
            raise ValueError("Candidate timestamps must be timezone aware")

        if self.last_seen < self.first_seen:
            raise ValueError("last_seen cannot precede first_seen")
