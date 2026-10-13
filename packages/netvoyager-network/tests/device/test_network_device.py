
"""Tests for physical network device identity, state, and metadata."""

from ipaddress import IPv4Address
from uuid import UUID

import pytest

from netvoyager_core.exceptions import NetVoyagerError
from netvoyager_network.device.models import NetworkDevice


def test_device_identity_is_deterministic():
    """Identical device names produce the same UUIDv5 identity."""
    first = NetworkDevice(name="12-SW-ACCESS-01")
    second = NetworkDevice(name="12-SW-ACCESS-01")

    assert first.device_id == second.device_id
    assert first.device_id.version == 5
    assert isinstance(first.device_id, UUID)


def test_different_names_have_different_identities():
    """Different inventory rows identify different physical devices."""
    first = NetworkDevice(name="12-SW-ACCESS-01")
    second = NetworkDevice(name="13-SW-ACCESS-01")

    assert first.device_id != second.device_id


def test_device_name_cannot_be_modified():
    """Reject changes to the device identity key."""
    device = NetworkDevice(name="12-SW-ACCESS-01")

    with pytest.raises(AttributeError):
        device.name = "13-SW-ACCESS-01"


def test_device_id_cannot_be_modified():
    """Reject direct reassignment of the generated identity."""
    device = NetworkDevice(name="12-SW-ACCESS-01")

    with pytest.raises(AttributeError):
        device.device_id = UUID(int=0)


def test_identical_devices_have_same_state():
    """Identical device attributes produce the same UUIDv5 state."""
    first = NetworkDevice(
        name="12-SW-ACCESS-01",
        serial_number="ABC123",
        management_ip=IPv4Address("10.1.1.10"),
    )

    second = NetworkDevice(
        name="12-SW-ACCESS-01",
        serial_number="ABC123",
        management_ip=IPv4Address("10.1.1.10"),
    )

    assert first.state_id == second.state_id
    assert first.state_id.version == 5


def test_serial_change_updates_state_not_identity():
    """Hardware replacement changes state without changing identity."""
    device = NetworkDevice(
        name="12-SW-ACCESS-01",
        serial_number="ABC123",
    )

    original_id = device.device_id
    original_state = device.state_id

    device.serial_number = "XYZ789"

    assert device.device_id == original_id
    assert device.state_id != original_state


def test_management_ip_change_updates_state():
    """Changing management IP produces a different state UUID."""
    device = NetworkDevice(
        name="12-SW-ACCESS-01",
        management_ip=IPv4Address("10.1.1.10"),
    )

    original_id = device.device_id
    original_state = device.state_id

    device.management_ip = IPv4Address("10.1.1.20")

    assert device.device_id == original_id
    assert device.state_id != original_state


def test_software_version_change_updates_state():
    """Software upgrades change technical state."""
    device = NetworkDevice(
        name="12-SW-ACCESS-01",
        software_version="17.9.4",
    )

    original_state = device.state_id

    device.software_version = "17.12.4"

    assert device.state_id != original_state


def test_hardware_replacement_preserves_identity():
    """Replacing physical hardware retains the inventory identity."""
    first = NetworkDevice(
        name="12-SW-ACCESS-01",
        manufacturer="Cisco",
        model="C3850",
        serial_number="ABC123",
    )

    replacement = NetworkDevice(
        name="12-SW-ACCESS-01",
        manufacturer="Cisco",
        model="C9300",
        serial_number="XYZ789",
    )

    assert first.device_id == replacement.device_id
    assert first.state_id != replacement.state_id


def test_state_restoration_is_deterministic():
    """Restoring previous attributes restores the original state UUID."""
    device = NetworkDevice(
        name="12-SW-ACCESS-01",
        status="active",
    )

    original_state = device.state_id

    device.status = "offline"
    assert device.state_id != original_state

    device.status = "active"
    assert device.state_id == original_state


def test_metadata_does_not_change_state():
    """Integration metadata does not participate in state identity."""
    device = NetworkDevice(name="12-SW-ACCESS-01")

    original_state = device.state_id

    device.update_metadata(
        "inventory",
        {"source": "excel", "row": 12},
    )

    assert device.state_id == original_state


def test_metadata_updates_merge_keys():
    """Updating a namespace preserves existing unrelated keys."""
    device = NetworkDevice(name="12-SW-ACCESS-01")

    device.update_metadata("inventory", {"source": "excel"})
    device.update_metadata("inventory", {"row": 12})

    assert device.get_metadata("inventory") == {
        "source": "excel",
        "row": 12,
    }


def test_metadata_is_deep_copied():
    """External changes cannot modify stored nested metadata."""
    device = NetworkDevice(name="12-SW-ACCESS-01")

    original = {"interfaces": ["Gi1/0/1"]}
    device.update_metadata("cisco", original)

    original["interfaces"].append("Gi1/0/2")

    assert device.get_metadata("cisco") == {
        "interfaces": ["Gi1/0/1"],
    }

    snapshot = device.get_metadata("cisco")
    snapshot["interfaces"].append("Gi1/0/3")

    assert device.get_metadata("cisco") == {
        "interfaces": ["Gi1/0/1"],
    }


def test_remove_metadata_namespace():
    """Removing metadata does not affect explicit device attributes."""
    device = NetworkDevice(
        name="12-SW-ACCESS-01",
        serial_number="ABC123",
    )

    device.update_metadata("inventory", {"source": "excel"})
    device.remove_metadata("inventory")

    assert device.get_metadata("inventory") == {}
    assert device.serial_number == "ABC123"


def test_invalid_metadata_namespace():
    """Reject invalid integration metadata namespace names."""
    device = NetworkDevice(name="12-SW-ACCESS-01")

    with pytest.raises(NetVoyagerError):
        device.update_metadata(" invalid ", {"value": 1})

    with pytest.raises(NetVoyagerError):
        device.get_metadata("")
