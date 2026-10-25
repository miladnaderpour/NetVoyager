
"""Tests for Excel SourceDataset normalization.

Verify that the Excel importer produces normalized DeviceObservation
records while retaining the detailed inventory reader for diagnostics.

All test data is synthetic.
"""

from pathlib import Path

from openpyxl import Workbook

from netvoyager_analysis.sources.models import SourceDataset
from netvoyager_import.inventory.excel import (
    read_excel_inventory,
    read_network_devices,
)


def make_workbook(path: Path) -> None:
    """Create a synthetic Excel network device inventory."""
    workbook = Workbook()
    sheet = workbook.active

    assert sheet is not None

    sheet.append([
        "name",
        "host_name",
        "site",
        "role",
        "primary_ipv4",
        "management_ip",
        "manufacturer",
        "model",
        "serial_number",
        "asset_tag",
        "software_version",
        "status",
        "validation_status",
    ])

    sheet.append([
        "FW-LAB-A",
        "fw-a.example.invalid",
        "LAB-A",
        "firewall",
        "192.0.2.11",
        "192.0.2.10",
        "Example Vendor",
        "Example Model",
        "TEST-001",
        "ASSET-001",
        "1.0",
        "active",
        "validated",
    ])

    sheet.append([
        "SW-LAB-B",
        "sw-b.example.invalid",
        "LAB-B",
        "switch",
        "198.51.100.11",
        "198.51.100.10",
        "Example Vendor",
        "Example Switch",
        "TEST-002",
        "ASSET-002",
        "2.0",
        "active",
        "validated",
    ])

    workbook.save(path)
    workbook.close()


def test_returns_normalized_dataset(tmp_path: Path):
    """The public device reader must return SourceDataset."""
    path = tmp_path / "inventory.xlsx"
    make_workbook(path)

    dataset = read_network_devices(path)

    assert isinstance(dataset, SourceDataset)
    assert dataset.source.name == "excel_inventory"
    assert dataset.source.source_type == "device_inventory"

    assert len(dataset.devices) == 2

    firewall = dataset.devices[0]

    assert firewall.inventory_name == "FW-LAB-A"
    assert firewall.hostname == "fw-a.example.invalid"
    assert firewall.serial_number == "TEST-001"
    assert firewall.site == "LAB-A"
    assert firewall.role == "firewall"
    assert firewall.asset_tag == "ASSET-001"
    assert firewall.primary_ipv4 == "192.0.2.11"
    assert firewall.management_ip == "192.0.2.10"
    assert firewall.manufacturer == "Example Vendor"
    assert firewall.model == "Example Model"
    assert firewall.software_version == "1.0"
    assert firewall.status == "active"
    assert firewall.validation_status == "validated"


def test_site_filter(tmp_path: Path):
    """Only devices from selected sites are normalized."""
    path = tmp_path / "inventory.xlsx"
    make_workbook(path)

    dataset = read_network_devices(
        path,
        sites={"LAB-A"},
    )

    assert isinstance(dataset, SourceDataset)
    assert len(dataset.devices) == 1

    device = dataset.devices[0]

    assert device.inventory_name == "FW-LAB-A"
    assert device.site == "LAB-A"


def test_device_filter(tmp_path: Path):
    """Device selection supports source serial numbers."""
    path = tmp_path / "inventory.xlsx"
    make_workbook(path)

    dataset = read_network_devices(
        path,
        devices={"TEST-002"},
    )

    assert isinstance(dataset, SourceDataset)
    assert len(dataset.devices) == 1

    device = dataset.devices[0]

    assert device.inventory_name == "SW-LAB-B"
    assert device.serial_number == "TEST-002"
    assert device.site == "LAB-B"


def test_original_reader_keeps_diagnostics(tmp_path: Path):
    """The detailed reader retains validation and IP-site mappings."""
    path = tmp_path / "inventory.xlsx"
    make_workbook(path)

    result = read_excel_inventory(path)

    assert len(result.observations) == 2
    assert result.issues == ()
    assert len(result.ip_sites_mapping) == 2

    assert result.observations[0].name == "FW-LAB-A"
    assert result.observations[0].site == "LAB-A"
    assert result.observations[0].line_number == 2

    assert result.observations[1].name == "SW-LAB-B"
    assert result.observations[1].site == "LAB-B"
    assert result.observations[1].line_number == 3


def test_source_identity_stable_observations_independent(
    tmp_path: Path,
):
    """Source identity is stable across independent imports."""
    path = tmp_path / "inventory.xlsx"
    make_workbook(path)

    first = read_network_devices(path)
    second = read_network_devices(path)

    assert isinstance(first, SourceDataset)
    assert isinstance(second, SourceDataset)

    assert first.source.source_id == second.source.source_id

    assert first.dataset_id != second.dataset_id

    assert len(first.devices) == len(second.devices) == 2

    assert (
        first.devices[0].observation_id
        != second.devices[0].observation_id
    )

    assert first.devices[0].serial_number == (
        second.devices[0].serial_number
    )
