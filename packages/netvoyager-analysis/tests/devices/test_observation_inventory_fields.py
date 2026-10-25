"""Tests for normalized device inventory observations."""

from uuid import UUID

import pytest

from netvoyager_analysis.devices.observations import DeviceObservation


def test_excel_inventory_attributes():
    observation = DeviceObservation(
        local_ref="excel:row:2",
        inventory_name="SW-LAB-01",
        hostname="sw-lab-01.example.invalid",
        serial_number="TEST-SERIAL-001",
        asset_tag="ASSET-001",
        management_ip="192.0.2.10",
        primary_ipv4="192.0.2.11",
        manufacturer="Example Vendor",
        model="Example Switch",
        software_version="1.0",
        role="access_switch",
        site="LAB-01",
        status="active",
        validation_status="validated",
    )

    assert observation.inventory_name == "SW-LAB-01"
    assert observation.site == "LAB-01"
    assert observation.role == "access_switch"
    assert observation.asset_tag == "ASSET-001"
    assert observation.primary_ipv4 == "192.0.2.11"
    assert observation.status == "active"
    assert observation.validation_status == "validated"
    assert isinstance(observation.observation_id, UUID)


def test_panorama_existing_constructor_remains_compatible():
    observation = DeviceObservation(
        local_ref="panorama:firewall:1",
        hostname="fw-lab.example.invalid",
        inventory_name="fw-lab.example.invalid",
        serial_number="TEST-FW-001",
        management_ip="198.51.100.10",
        manufacturer="Palo Alto Networks",
    )

    assert observation.hostname == "fw-lab.example.invalid"
    assert observation.serial_number == "TEST-FW-001"

    assert observation.site is None
    assert observation.role is None
    assert observation.asset_tag is None
    assert observation.primary_ipv4 is None
    assert observation.status is None
    assert observation.validation_status is None


def test_observation_identities_are_independent():
    first = DeviceObservation(local_ref="excel:row:2")
    second = DeviceObservation(local_ref="excel:row:2")

    assert first.observation_id != second.observation_id


@pytest.mark.parametrize("local_ref", ["", "   "])
def test_empty_local_ref_rejected(local_ref):
    with pytest.raises(ValueError):
        DeviceObservation(local_ref=local_ref)