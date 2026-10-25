
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
    """Convert a discovery candidate into a persistence entity.

    Preserve candidate UUID, lifecycle, reported inventory attributes,
    discovery timestamps, and authorized canonical resolution.
    """
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
        site=candidate.site,
        role=candidate.role,
        primary_ipv4=(
            str(candidate.primary_ipv4)
            if candidate.primary_ipv4 is not None
            else None
        ),
        manufacturer=candidate.manufacturer,
        model=candidate.model,
        software_version=candidate.software_version,
        asset_tag=candidate.asset_tag,
        first_seen=_as_utc(candidate.first_seen),
        last_seen=_as_utc(candidate.last_seen),
        resolved_device_id=candidate.resolved_device_id,
    )


def candidate_to_domain(
    entity: DeviceDiscoveryCandidateEntity,
) -> DeviceDiscoveryCandidate:
    """Reconstruct an immutable candidate from SQL persistence.

    Reported inventory attributes remain provisional even when a
    candidate has been resolved to an existing canonical device.
    """
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
        site=entity.site,
        role=entity.role,
        primary_ipv4=(
            IPv4Address(entity.primary_ipv4)
            if entity.primary_ipv4 is not None
            else None
        ),
        manufacturer=entity.manufacturer,
        model=entity.model,
        software_version=entity.software_version,
        asset_tag=entity.asset_tag,
        first_seen=_as_utc(entity.first_seen),
        last_seen=_as_utc(entity.last_seen),
        resolved_device_id=entity.resolved_device_id,
    )
