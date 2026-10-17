"""Pure comparisons of candidate and canonical physical-device identities.

Evidence, policy authorization, and relationship mutation are outside this module.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, TypeAlias
from uuid import UUID

from netvoyager_network.device.models import NetworkDevice

from .discovery.models import DeviceDiscoveryCandidate
from .matching_rules import DEFAULT_DEVICE_MATCHING_RULES, DeviceMatchingRules, SourceRef

DeviceIdentityObject: TypeAlias = DeviceDiscoveryCandidate | NetworkDevice
MatchMethod: TypeAlias = Literal[
    "exact_serial", "numeric_leading_zero_loss", "hostname", "management_ip",
]


@dataclass(frozen=True, slots=True)
class IdentityTarget:
    """An existing domain object with explicitly supplied source context."""

    device: DeviceIdentityObject
    source: SourceRef | None = None

    @property
    def object_id(self) -> UUID:
        return (
            self.device.device_id if isinstance(self.device, NetworkDevice)
            else self.device.candidate_id
        )

    @property
    def object_type(self) -> Literal["network_device", "device_discovery_candidate"]:
        return (
            "network_device" if isinstance(self.device, NetworkDevice)
            else "device_discovery_candidate"
        )


@dataclass(frozen=True, slots=True)
class CandidateMatchSignal:
    """One matching attribute; it is not an identity decision."""

    method: MatchMethod
    rule_name: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateMatch:
    """Potential correspondence, including weak signals."""

    left: IdentityTarget
    right: IdentityTarget
    signals: tuple[CandidateMatchSignal, ...]

    @property
    def has_serial_match(self) -> bool:
        return any(s.method in {"exact_serial", "numeric_leading_zero_loss"} for s in self.signals)


@dataclass(frozen=True, slots=True)
class CandidateMatchingResult:
    target: IdentityTarget
    matches: tuple[CandidateMatch, ...]


def _text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().casefold() or None


def _serial(value: str | None) -> str | None:
    normalized = _text(value)
    if normalized in {None, "unknown", "none", "null", "n/a", "na", "0"}:
        return None
    return normalized


def compare_identity_targets(
    left: IdentityTarget,
    right: IdentityTarget,
    *,
    rules: DeviceMatchingRules = DEFAULT_DEVICE_MATCHING_RULES,
) -> CandidateMatch | None:
    """Find correspondence without inferring trust or modifying objects.

    Different valid serial numbers veto weaker correlations, unless an
    explicitly permitted source-pair comparison reconciles them.
    """
    if (left.object_type, left.object_id) == (right.object_type, right.object_id):
        return None

    signals: list[CandidateMatchSignal] = []
    a, b = left.device, right.device
    serial_a, serial_b = _serial(a.serial_number), _serial(b.serial_number)

    if serial_a is not None and serial_b is not None:
        if serial_a == serial_b:
            signals.append(CandidateMatchSignal("exact_serial", "exact_serial"))
        elif left.source is not None and right.source is not None:
            comparison = rules.compare_serials(
                a.serial_number, b.serial_number,
                left_source=left.source, right_source=right.source,
            )
            if comparison is not None:
                signals.append(CandidateMatchSignal(comparison.method, comparison.rule_name))
        if not signals:
            return None

    if _text(a.host_name) is not None and _text(a.host_name) == _text(b.host_name):
        signals.append(CandidateMatchSignal("hostname"))
    if a.management_ip is not None and a.management_ip == b.management_ip:
        signals.append(CandidateMatchSignal("management_ip"))

    return CandidateMatch(left, right, tuple(signals)) if signals else None


def match_device_candidates(
    target: IdentityTarget,
    candidates: Iterable[IdentityTarget],
    *,
    rules: DeviceMatchingRules = DEFAULT_DEVICE_MATCHING_RULES,
) -> CandidateMatchingResult:
    """Return all candidate/canonical potential matches, without decisions."""
    matches: list[CandidateMatch] = []
    seen: set[tuple[str, UUID]] = set()
    for other in candidates:
        key = (other.object_type, other.object_id)
        if key in seen:
            continue
        seen.add(key)
        match = compare_identity_targets(target, other, rules=rules)
        if match is not None:
            matches.append(match)
    return CandidateMatchingResult(target, tuple(matches))
