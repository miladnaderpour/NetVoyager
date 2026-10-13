
"""Tests for duplicate handling in Excel device inventories."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from netvoyager_import.inventory.excel import read_network_devices


def create_inventory(
    path: Path,
    records: list[tuple[str, str | None]],
) -> Path:
    """Create a minimal inventory workbook for testing."""
    workbook = Workbook()
    sheet = workbook.active

    assert sheet is not None

    sheet.append([
        "name",
        "site",
        "management_ip",
        "serial_number",
    ])

    for name, serial in records:
        sheet.append([
            name,
            "SITE01",
            "10.1.1.10",
            serial,
        ])

    workbook.save(path)
    workbook.close()

    return path


def test_unique_names_remain_unchanged(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW02", "XYZ789"),
        ],
    )

    result = read_network_devices(path)

    assert [item.name for item in result.observations] == [
        "SW01",
        "SW02",
    ]
    assert result.issues == ()


def test_duplicate_names_receive_row_prefix(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW01", "XYZ789"),
            ("SW02", "DEF456"),
        ],
    )

    result = read_network_devices(path)

    assert [item.name for item in result.observations] == [
        "DUP-2-SW01",
        "DUP-3-SW01",
        "SW02",
    ]

    assert sum(
        "Duplicate device name" in issue.reason
        for issue in result.issues
    ) == 2


def test_duplicate_names_are_case_insensitive(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("sw01", "XYZ789"),
        ],
    )

    result = read_network_devices(path)

    assert [item.name for item in result.observations] == [
        "DUP-2-SW01",
        "DUP-3-sw01",
    ]


def test_generated_name_collision_is_resolved(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW01", "XYZ789"),
            ("DUP-2-SW01", "DEF456"),
        ],
    )

    result = read_network_devices(path)

    assert [item.name for item in result.observations] == [
        "DUP-2-SW01-2",
        "DUP-3-SW01",
        "DUP-2-SW01",
    ]


def test_duplicate_name_warn_preserves_names(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW01", "XYZ789"),
        ],
    )

    result = read_network_devices(
        path,
        duplicate_name_policy="warn",
    )

    assert [item.name for item in result.observations] == [
        "SW01",
        "SW01",
    ]

    assert len(result.issues) == 2


def test_duplicate_name_error_raises(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW01", "XYZ789"),
        ],
    )

    with pytest.raises(ValueError, match="Duplicate device name"):
        read_network_devices(
            path,
            duplicate_name_policy="error",
        )


def test_duplicate_serial_warns_without_renaming(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW02", "ABC123"),
        ],
    )

    result = read_network_devices(path)

    assert [item.name for item in result.observations] == [
        "SW01",
        "SW02",
    ]

    assert sum(
        "Duplicate serial number" in issue.reason
        for issue in result.issues
    ) == 2


def test_duplicate_serial_error_raises(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW02", "ABC123"),
        ],
    )

    with pytest.raises(ValueError, match="Duplicate serial number"):
        read_network_devices(
            path,
            duplicate_serial_policy="error",
        )


def test_placeholder_serials_are_ignored(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "N/A"),
            ("SW02", "Unknown"),
            ("SW03", "N/A"),
            ("SW04", None),
        ],
    )

    result = read_network_devices(path)

    assert not any(
        "Duplicate serial number" in issue.reason
        for issue in result.issues
    )


def test_original_inventory_line_is_preserved(tmp_path: Path):
    path = create_inventory(
        tmp_path / "inventory.xlsx",
        [
            ("SW01", "ABC123"),
            ("SW01", "XYZ789"),
        ],
    )

    result = read_network_devices(path)

    observation = result.observations[0]

    assert observation.name == "DUP-2-SW01"
    assert observation.line_number == 2
    assert "name=SW01" in observation.raw_line


def test_invalid_policy_is_rejected(tmp_path: Path):
    path = tmp_path / "inventory.xlsx"

    with pytest.raises(ValueError, match="Invalid duplicate name policy"):
        read_network_devices(
            path,
            duplicate_name_policy="invalid",
        )
