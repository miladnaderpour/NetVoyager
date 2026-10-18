
"""Map discovery candidates between domain and SQLAlchemy entities."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import cast

from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
    DeviceDiscoveryCandidateStatus,
)

from netvoyager_database.entities.devices.discovery_candidate import (
    DeviceDiscoveryCandidateEntity,
)


def _as_utc(value: datetime) -> datetime:
    """Normalize an aware timestamp or restore stored UTC timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def _candidate_status(value: str) -> DeviceDiscoveryCandidateStatus:
    """Validate and narrow a persisted candidate status."""
    if value not in {
        "candidate",
        "corroborated",
        "resolved",
        "rejected",
        "retired",
    }:
        raise ValueError(f"Invalid stored candidate status: {value}")

    return cast(DeviceDiscoveryCandidateStatus, value)


def candidate_to_entity(
    candidate: DeviceDiscoveryCandidate,
) -> DeviceDiscoveryCandidateEntity:
    """Convert a discovery candidate into a persistence entity."""
    return DeviceDiscoveryCandidateEntity(
        candidate_id=candidate.candidate_id,
        status=candidate.status,
        name=candidate.name,
        host_name=candidate.host_name,
        serial_number=candidate.serial_number,
        management_ip=(
            str(candidate.management_ip)
            if candidate.management_ip is not None
            else None
        ),
        first_seen=_as_utc(candidate.first_seen),
        last_seen=_as_utc(candidate.last_seen),
        resolved_device_id=candidate.resolved_device_id,
    )


def candidate_to_domain(
    entity: DeviceDiscoveryCandidateEntity,
) -> DeviceDiscoveryCandidate:
    """Reconstruct an immutable discovery candidate from persistence."""
    return DeviceDiscoveryCandidate(
        candidate_id=entity.candidate_id,
        status=_candidate_status(entity.status),
        name=entity.name,
        host_name=entity.host_name,
        serial_number=entity.serial_number,
        management_ip=(
            IPv4Address(entity.management_ip)
            if entity.management_ip is not None
            else None
        ),
        first_seen=_as_utc(entity.first_seen),
        last_seen=_as_utc(entity.last_seen),
        resolved_device_id=entity.resolved_device_id,
    )
