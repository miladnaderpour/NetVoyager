"""Match device identity observations to existing network devices."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from netvoyager_core.logging import get_logger
from netvoyager_network.device.models import NetworkDevice

from .protocols import DeviceIdentityObservation


logger = get_logger("netvoyager.analysis.devices.matching")


MatchMethod = Literal[
    "serial",
    "hostname",
    "management_ip",
    "hostname+management_ip",
]


@dataclass(frozen=True, slots=True)
class DeviceMatch:
    """Resolved match between a source observation and network device."""

    observation: DeviceIdentityObservation
    device: NetworkDevice
    matched_by: MatchMethod


@dataclass(frozen=True, slots=True)
class UnresolvedDeviceMatch:
    """Source observation that could not be resolved safely."""

    observation: DeviceIdentityObservation
    reason: str
    candidates: tuple[NetworkDevice, ...] = ()


@dataclass(frozen=True, slots=True)
class DeviceMatchingResult:
    """Result of matching device identity observations."""

    matches: tuple[DeviceMatch, ...]
    unresolved: tuple[UnresolvedDeviceMatch, ...]


def _normalize_text(value: str | None) -> str | None:
    """Normalize textual identity values for comparison."""
    if value is None:
        return None

    value = value.strip()

    return value.casefold() if value else None


def _unique_devices(
    devices: Iterable[NetworkDevice],
) -> tuple[NetworkDevice, ...]:
    """Return devices uniquely keyed by device UUID."""
    return tuple({
        device.device_id: device
        for device in devices
    }.values())


def match_devices(
    observations: Iterable[DeviceIdentityObservation],
    devices: Iterable[NetworkDevice],
) -> DeviceMatchingResult:
    """Match source observations against existing network devices.

    Matching precedence:

    1. A unique serial-number match is accepted immediately.
    2. Without a serial match, hostname and management IP are compared.
    3. If hostname and management IP identify the same unique device,
       the observation is matched using both signals.
    4. A unique hostname match may be accepted independently.
    5. A unique management-IP match may be accepted independently.
    6. Ambiguous or conflicting observations remain unresolved.

    This function does not create, modify, or merge devices.
    """
    device_list = list(devices)

    matches: list[DeviceMatch] = []
    unresolved: list[UnresolvedDeviceMatch] = []

    observation_count = 0

    for observation in observations:
        observation_count += 1

        serial = _normalize_text(observation.serial_number)
        hostname = _normalize_text(
            observation.host_name or observation.name
        )

        serial_matches = [
            device
            for device in device_list
            if (
                serial is not None
                and _normalize_text(device.serial_number) == serial
            )
        ]

        if len(serial_matches) == 1:
            match = DeviceMatch(
                observation=observation,
                device=serial_matches[0],
                matched_by="serial",
            )
            matches.append(match)

            logger.debug(
                "Device matched by serial: "
                "serial=%s | device=%s | device_id=%s",
                observation.serial_number,
                match.device.name,
                match.device.device_id,
            )
            continue

        if len(serial_matches) > 1:
            unresolved.append(
                UnresolvedDeviceMatch(
                    observation=observation,
                    reason="Serial number matches multiple devices",
                    candidates=tuple(serial_matches),
                )
            )
            continue

        hostname_matches = [
            device
            for device in device_list
            if (
                hostname is not None
                and hostname
                in {
                    _normalize_text(device.name),
                    _normalize_text(device.host_name),
                }
            )
        ]

        management_ip_matches = [
            device
            for device in device_list
            if (
                observation.management_ip is not None
                and device.management_ip == observation.management_ip
            )
        ]

        hostname_ids = {
            device.device_id
            for device in hostname_matches
        }
        management_ip_ids = {
            device.device_id
            for device in management_ip_matches
        }

        if hostname_ids and management_ip_ids:
            common_ids = hostname_ids & management_ip_ids

            common_devices = [
                device
                for device in device_list
                if device.device_id in common_ids
            ]

            if len(common_devices) == 1:
                match = DeviceMatch(
                    observation=observation,
                    device=common_devices[0],
                    matched_by="hostname+management_ip",
                )
                matches.append(match)

                logger.debug(
                    "Device matched by hostname and management IP: "
                    "hostname=%s | management_ip=%s | "
                    "device=%s | device_id=%s",
                    hostname,
                    observation.management_ip,
                    match.device.name,
                    match.device.device_id,
                )
                continue

            candidates = _unique_devices(
                hostname_matches + management_ip_matches
            )

            unresolved.append(
                UnresolvedDeviceMatch(
                    observation=observation,
                    reason=(
                        "Hostname and management IP produce "
                        "conflicting or ambiguous candidates"
                    ),
                    candidates=candidates,
                )
            )
            continue

        if len(hostname_matches) == 1:
            match = DeviceMatch(
                observation=observation,
                device=hostname_matches[0],
                matched_by="hostname",
            )
            matches.append(match)

            logger.debug(
                "Device matched by hostname: "
                "hostname=%s | device=%s | device_id=%s",
                hostname,
                match.device.name,
                match.device.device_id,
            )
            continue

        if len(management_ip_matches) == 1:
            match = DeviceMatch(
                observation=observation,
                device=management_ip_matches[0],
                matched_by="management_ip",
            )
            matches.append(match)

            logger.debug(
                "Device matched by management IP: "
                "management_ip=%s | device=%s | device_id=%s",
                observation.management_ip,
                match.device.name,
                match.device.device_id,
            )
            continue

        candidates = _unique_devices(
            hostname_matches + management_ip_matches
        )

        unresolved.append(
            UnresolvedDeviceMatch(
                observation=observation,
                reason=(
                    "Multiple candidate devices found"
                    if candidates
                    else "No matching device found"
                ),
                candidates=candidates,
            )
        )

    logger.info(
        "Device matching complete: observations=%d, "
        "matched=%d, unresolved=%d",
        observation_count,
        len(matches),
        len(unresolved),
    )

    return DeviceMatchingResult(
        matches=tuple(matches),
        unresolved=tuple(unresolved),
    )