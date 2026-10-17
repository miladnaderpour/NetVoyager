"""Read-only checks of physical-device identity using domain objects.

Evidence lookup and policy authorization are responsibilities of other layers.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, TypeAlias
from uuid import UUID

from netvoyager_network.device.models import NetworkDevice

from .candidate_matching import (
    CandidateMatch, CandidateMatchingResult, IdentityTarget,
    _serial, compare_identity_targets,
)
from .matching_rules import DEFAULT_DEVICE_MATCHING_RULES, DeviceMatchingRules

IdentityValidationStatus: TypeAlias = Literal["verified", "unresolved", "conflict"]


@dataclass(frozen=True, slots=True)
class IdentityValidationResult:
    """Validation finding, not source authorization or a store decision."""

    status: IdentityValidationStatus
    reason: str
    valid_physical_serial: bool = False
    unique_physical_serial: bool = False
    unambiguous_device_match: bool = False
    matched_device_id: UUID | None = None

    @property
    def verified(self) -> bool:
        return self.status == "verified"


class IdentityValidator:
    """Check pairwise identity and conflicts with existing canonical devices."""

    def __init__(self, *, rules: DeviceMatchingRules = DEFAULT_DEVICE_MATCHING_RULES) -> None:
        self._rules = rules

    def validate_match(self, match: CandidateMatch) -> IdentityValidationResult:
        """Require serial correspondence; weak signals never establish identity."""
        current = compare_identity_targets(match.left, match.right, rules=self._rules)
        if current is None or not current.has_serial_match:
            return IdentityValidationResult("unresolved", "No validated physical-serial correspondence")
        return IdentityValidationResult(
            "verified", "Physical serial correspondence verified",
            valid_physical_serial=True,
        )

    def validate_canonical_identity(
        self,
        target: IdentityTarget,
        *,
        canonical_devices: Iterable[IdentityTarget | NetworkDevice],
    ) -> IdentityValidationResult:
        """Find zero, one, or conflicting existing canonical device identities.

        Callers may pass IdentityTarget for source-aware serial comparison.
        A bare NetworkDevice is compared by exact serial only.
        Inventory completeness and source trust must be established upstream.
        """
        if _serial(target.device.serial_number) is None:
            return IdentityValidationResult("unresolved", "Missing or invalid physical serial")

        matches: set[UUID] = set()
        for item in canonical_devices:
            device = item if isinstance(item, IdentityTarget) else IdentityTarget(item)
            if not isinstance(device.device, NetworkDevice):
                raise TypeError("canonical_devices must contain NetworkDevice objects")
            comparison = compare_identity_targets(target, device, rules=self._rules)
            if comparison is not None and comparison.has_serial_match:
                matches.add(device.device.device_id)

        if len(matches) > 1:
            return IdentityValidationResult(
                "conflict", "Serial corresponds to multiple canonical device identities",
                valid_physical_serial=True,
            )
        existing = next(iter(matches)) if matches else None
        return IdentityValidationResult(
            "verified",
            "Existing canonical identity found" if existing else "No canonical identity found in supplied inventory",
            valid_physical_serial=True,
            unique_physical_serial=True,
            unambiguous_device_match=True,
            matched_device_id=existing,
        )

    def validate_candidate_matches(
        self, result: CandidateMatchingResult,
    ) -> tuple[IdentityValidationResult, ...]:
        """Validate pairs individually; additional candidates do not imply conflict."""
        return tuple(self.validate_match(match) for match in result.matches)
