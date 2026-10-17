
"""Tests for source-aware device serial matching rules."""

from netvoyager_analysis.devices.matching_rules import (
    DEFAULT_DEVICE_MATCHING_RULES,
    SourceRef,
)


EXCEL = SourceRef(
    source_id="excel_inventory",
    method="device_inventory",
)

PANORAMA = SourceRef(
    source_id="paloalto_panorama",
    method="managed_device_inventory",
)

OTHER = SourceRef(
    source_id="other",
    method="device_inventory",
)


def compare(
    left: str | None,
    right: str | None,
    *,
    left_source: SourceRef = EXCEL,
    right_source: SourceRef = PANORAMA,
):
    """Compare serials using the default matching rules."""
    return DEFAULT_DEVICE_MATCHING_RULES.compare_serials(
        left,
        right,
        left_source=left_source,
        right_source=right_source,
    )


def test_exact_serial_match() -> None:
    result = compare("123456789", "123456789")

    assert result is not None
    assert result.method == "exact_serial"


def test_leading_zero_loss() -> None:
    result = compare("123456789", "00123456789")

    assert result is not None
    assert result.method == "numeric_leading_zero_loss"
    assert result.rule_name == "excel_panorama_leading_zero_loss"


def test_multiple_leading_zeros() -> None:
    assert compare("123456789", "000123456789") is not None


def test_matching_is_symmetric() -> None:
    result = compare(
        "00123456789",
        "123456789",
        left_source=PANORAMA,
        right_source=EXCEL,
    )

    assert result is not None
    assert result.method == "numeric_leading_zero_loss"


def test_normalization_is_source_specific() -> None:
    result = compare(
        "123456789",
        "00123456789",
        left_source=OTHER,
    )

    assert result is None


def test_normalization_is_directional_by_source() -> None:
    result = compare(
        "00123456789",
        "123456789",
        left_source=EXCEL,
        right_source=PANORAMA,
    )

    assert result is None


def test_alphanumeric_serials_are_not_stripped() -> None:
    assert compare("ABC123", "00ABC123") is None


def test_unrelated_serials_do_not_match() -> None:
    assert compare("123456789", "987654321") is None


def test_missing_serials_do_not_match() -> None:
    assert compare(None, "00123456789") is None
    assert compare("", "00123456789") is None


def test_zero_only_serials_do_not_match_by_normalization() -> None:
    assert compare("0", "000") is None


def test_whitespace_is_ignored() -> None:
    result = compare(" 123456789 ", " 00123456789 ")

    assert result is not None
    assert result.method == "numeric_leading_zero_loss"


def test_exact_matching_does_not_require_special_rule() -> None:
    result = compare(
        "ABC123",
        "abc123",
        left_source=OTHER,
        right_source=PANORAMA,
    )

    assert result is not None
    assert result.method == "exact_serial"
