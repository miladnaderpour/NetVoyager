"""Legacy observation-to-canonical matching adapter.

Only unambiguous physical serial matches are resolved. Hostname and
management IP are weak hints, never canonical identity proof. New callers
should use candidate_matching instead.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from netvoyager_network.device.models import NetworkDevice

from .matching_rules import DEFAULT_DEVICE_MATCHING_RULES, DeviceMatchingRules, SourceRef
from .protocols import DeviceIdentityObservation

MatchMethod = Literal["serial", "serial_without_leading_zero", "hostname", "management_ip", "hostname+management_ip"]

@dataclass(frozen=True, slots=True)
class DeviceMatch:
    observation: DeviceIdentityObservation
    device: NetworkDevice
    matched_by: MatchMethod

@dataclass(frozen=True, slots=True)
class UnresolvedDeviceMatch:
    observation: DeviceIdentityObservation
    reason: str
    candidates: tuple[NetworkDevice, ...] = ()

@dataclass(frozen=True, slots=True)
class DeviceMatchingResult:
    matches: tuple[DeviceMatch, ...]
    unresolved: tuple[UnresolvedDeviceMatch, ...]

def match_devices(
    observations: Iterable[DeviceIdentityObservation],
    devices: Iterable[NetworkDevice],
    *,
    observation_source: SourceRef | None = None,
    device_source: SourceRef | None = None,
    rules: DeviceMatchingRules = DEFAULT_DEVICE_MATCHING_RULES,
) -> DeviceMatchingResult:
    """Only return strong, unique serial matches; preserve unresolved hints."""
    inventory = tuple(devices)
    matched: list[DeviceMatch] = []
    unresolved: list[UnresolvedDeviceMatch] = []
    for observation in observations:
        serial = observation.serial_number
        serial = serial.strip() if isinstance(serial, str) else ""
        if not serial or serial.casefold() in {"unknown", "none", "null", "na", "n/a", "0"}:
            unresolved.append(UnresolvedDeviceMatch(observation, "No valid physical serial"))
            continue
        strong: dict[object, tuple[NetworkDevice, MatchMethod]] = {}
        for device in inventory:
            result = None
            other = device.serial_number
            if other and other.strip().casefold() == serial.casefold():
                strong[device.device_id] = (device, "serial")
            elif observation_source is not None and device_source is not None:
                result = rules.compare_serials(serial, other, left_source=observation_source, right_source=device_source)
                if result is not None:
                    strong[device.device_id] = (device, "serial_without_leading_zero")
        if len(strong) == 1:
            device, method = next(iter(strong.values()))
            matched.append(DeviceMatch(observation, device, method))
        else:
            unresolved.append(UnresolvedDeviceMatch(
                observation,
                "Multiple canonical identities share physical serial" if strong else "No canonical physical serial match",
                tuple(value[0] for value in strong.values()),
            ))
    return DeviceMatchingResult(tuple(matched), tuple(unresolved))
