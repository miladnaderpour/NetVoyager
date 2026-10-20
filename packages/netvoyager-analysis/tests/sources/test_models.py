"""Tests for standardized source datasets."""

from netvoyager_analysis.devices.observations import DeviceObservation
from netvoyager_analysis.neighbors.observations import NeighborObservation
from netvoyager_analysis.sources.models import Source, SourceDataset


def test_source_dataset_with_device_and_neighbor() -> None:
    """Represent a collected device and an unresolved neighbor."""

    source = Source(
        name="Test Router Collection",
        source_type="ssh_text",
    )

    device = DeviceObservation(
        local_ref="device-1",
        hostname="switch-test-01",
        inventory_name="inventory-device-001",
        serial_number="TEST-SERIAL-001",
        management_ip="192.0.2.10",
        manufacturer="ExampleVendor",
        model="TEST-SWITCH",
        software_version="1.0.0",
    )

    neighbor = NeighborObservation(
        local_device_ref="device-1",
        local_interface="GigabitEthernet1/0/1",
        protocol="cdp",
        remote_device_name="ap-test-01",
        remote_interface="GigabitEthernet0",
        remote_management_ip="192.0.2.20",
        remote_platform="TEST-AP",
    )

    dataset = SourceDataset(
        source=source,
        devices=(device,),
        neighbors=(neighbor,),
    )

    assert len(dataset.devices) == 1
    assert len(dataset.neighbors) == 1
    assert dataset.devices[0].serial_number == "TEST-SERIAL-001"
    assert dataset.devices[0].hostname == "switch-test-01"
    assert dataset.neighbors[0].local_device_ref == device.local_ref
    assert dataset.neighbors[0].remote_device_name == "ap-test-01"


def test_observations_have_independent_ids() -> None:
    """Repeated observations retain separate identities."""

    first = DeviceObservation(
        local_ref="device-1",
        serial_number="TEST-SERIAL-001",
    )

    second = DeviceObservation(
        local_ref="device-1",
        serial_number="TEST-SERIAL-001",
    )

    assert first.observation_id != second.observation_id