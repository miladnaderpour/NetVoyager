
"""Source-aware rules for comparing physical device identifiers.

Matching rules define permitted identifier comparisons, not device
identity decisions. They do not evaluate source authority, modify
candidates, or authorize reconciliation.

Rule definitions are independent of their storage representation so
they can be loaded from external configuration in the future.
"""

from dataclasses import dataclass
from typing import Literal, TypeAlias


SerialMatchMethod: TypeAlias = Literal[
    "exact_serial",
    "numeric_leading_zero_loss",
]


@dataclass(frozen=True, slots=True)
class SourceRef:
    """Identify a source and its collection method."""

    source_id: str
    method: str

    def __post_init__(self) -> None:
        """Validate the source identifier."""
        if not self.source_id.strip():
            raise ValueError("Source ID cannot be empty")

        if not self.method.strip():
            raise ValueError("Collection method cannot be empty")


@dataclass(frozen=True, slots=True)
class SerialMatchingRule:
    """Define a permitted serial comparison between two sources.

    The comparison is symmetric, but normalization is applied only
    when the affected and reference sources are correctly identified.
    """

    name: str
    method: SerialMatchMethod

    affected_source: SourceRef
    reference_source: SourceRef

    def __post_init__(self) -> None:
        """Validate the rule definition."""
        if not self.name.strip():
            raise ValueError("Matching rule name cannot be empty")

        if self.method not in {
            "exact_serial",
            "numeric_leading_zero_loss",
        }:
            raise ValueError(
                f"Unsupported serial matching method: {self.method}"
            )

        if self.affected_source == self.reference_source:
            raise ValueError(
                "Source-specific rules require distinct source references"
            )


@dataclass(frozen=True, slots=True)
class SerialMatchResult:
    """Describe a successful serial comparison.

    A successful comparison is not proof of unique physical identity.
    """

    method: SerialMatchMethod
    rule_name: str
    left_serial: str
    right_serial: str


@dataclass(frozen=True, slots=True)
class DeviceMatchingRules:
    """Hold immutable source-aware serial matching rules."""

    serial_rules: tuple[SerialMatchingRule, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate matching rule names."""
        names = [rule.name for rule in self.serial_rules]

        if len(names) != len(set(names)):
            raise ValueError(
                "Duplicate matching rule names are not allowed"
            )

    def compare_serials(
        self,
        left_serial: str | None,
        right_serial: str | None,
        *,
        left_source: SourceRef,
        right_source: SourceRef,
    ) -> SerialMatchResult | None:
        """Compare serials using exact and permitted source-aware rules.

        Exact matching is attempted first. Source-specific normalization
        requires a matching rule and the correct source provenance.

        This method does not establish uniqueness or identity authority.
        """
        left = _normalize_serial(left_serial)
        right = _normalize_serial(right_serial)

        if left is None or right is None:
            return None

        if left == right:
            return SerialMatchResult(
                method="exact_serial",
                rule_name="exact_serial",
                left_serial=left_serial,
                right_serial=right_serial,
            )

        for rule in self.serial_rules:
            if rule.method != "numeric_leading_zero_loss":
                continue

            if (
                left_source == rule.affected_source
                and right_source == rule.reference_source
            ):
                affected, reference = left, right

            elif (
                right_source == rule.affected_source
                and left_source == rule.reference_source
            ):
                affected, reference = right, left

            else:
                continue

            if _matches_leading_zero_loss(
                affected,
                reference,
            ):
                return SerialMatchResult(
                    method=rule.method,
                    rule_name=rule.name,
                    left_serial=left_serial,
                    right_serial=right_serial,
                )

        return None


def _normalize_serial(value: str | None) -> str | None:
    """Normalize whitespace and case without removing leading zeros."""
    if value is None:
        return None

    normalized = value.strip().casefold()
    return normalized or None


def _matches_leading_zero_loss(
    affected: str,
    reference: str,
) -> bool:
    """Check whether a numeric serial lost leading zeros in one source.

    Only the affected source may have lost zeros. The reference must
    contain a genuine leading-zero prefix, and the remaining serial
    must contain at least one nonzero digit.

    Non-numeric identifiers are never processed by this rule.
    """
    if not affected.isascii() or not reference.isascii():
        return False

    if not affected.isdecimal() or not reference.isdecimal():
        return False

    if not reference.startswith("0"):
        return False

    normalized_reference = reference.lstrip("0")

    if not normalized_reference:
        return False

    return affected == normalized_reference


DEFAULT_DEVICE_MATCHING_RULES = DeviceMatchingRules(
    serial_rules=(
        SerialMatchingRule(
            name="excel_panorama_leading_zero_loss",
            method="numeric_leading_zero_loss",
            affected_source=SourceRef(
                source_id="excel_inventory",
                method="device_inventory",
            ),
            reference_source=SourceRef(
                source_id="paloalto_panorama",
                method="managed_device_inventory",
            ),
        ),
    ),
)
