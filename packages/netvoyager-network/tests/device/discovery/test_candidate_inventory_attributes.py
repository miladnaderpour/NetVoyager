
"""Tests for extended device discovery candidate inventory attributes.

All device names, addresses, serials, and sites are synthetic.
"""

from dataclasses import replace
from ipaddress import IPv4Address
from uuid import uuid4

import pytest

from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


def test_candidate_preserves_inventory_attributes():
    candidate = DeviceDiscoveryCandidate(
        name="SW-LAB-01",
        host_name="sw-lab-01.example.invalid",
        serial_number="TEST-SERIAL-001",
        management_ip=IPv4Address("192.0.2.10"),
        site="LAB-A",
        role="access_switch",
        primary_ipv4=IPv4Address("192.0.2.11"),
        manufacturer="Example Vendor",
        model="Example Switch",
        software_version="1.0",
        asset_tag="TEST-ASSET-001",
    )

    assert candidate.name == "SW-LAB-01"
    assert candidate.site == "LAB-A"
    assert candidate.role == "access_switch"
    assert candidate.primary_ipv4 == IPv4Address("192.0.2.11")
    assert candidate.manufacturer == "Example Vendor"
    assert candidate.model == "Example Switch"
    assert candidate.software_version == "1.0"
    assert candidate.asset_tag == "TEST-ASSET-001"
    assert candidate.status == "candidate"
    assert candidate.resolved_device_id is None


def test_inventory_attributes_are_optional():
    candidate = DeviceDiscoveryCandidate(
        name="FW-LAB-01",
        serial_number="TEST-SERIAL-002",
    )

    assert candidate.site is None
    assert candidate.role is None
    assert candidate.primary_ipv4 is None
    assert candidate.manufacturer is None
    assert candidate.model is None
    assert candidate.software_version is None
    assert candidate.asset_tag is None


def test_inventory_update_preserves_candidate_identity():
    original = DeviceDiscoveryCandidate(
        name="SW-LAB-01",
        serial_number="TEST-SERIAL-003",
    )

    updated = replace(
        original,
        site="LAB-B",
        role="distribution_switch",
        manufacturer="Example Vendor",
    )

    assert updated.candidate_id == original.candidate_id
    assert updated.status == original.status
    assert updated.site == "LAB-B"
    assert original.site is None


def test_reported_site_does_not_resolve_candidate():
    candidate = DeviceDiscoveryCandidate(
        name="FW-LAB-01",
        site="LAB-A",
    )

    assert candidate.status == "candidate"
    assert candidate.resolved_device_id is None


def test_resolved_candidate_retains_inventory_attributes():
    device_id = uuid4()

    candidate = DeviceDiscoveryCandidate(
        name="FW-LAB-01",
        site="LAB-A",
        manufacturer="Example Vendor",
        status="resolved",
        resolved_device_id=device_id,
    )

    assert candidate.status == "resolved"
    assert candidate.resolved_device_id == device_id
    assert candidate.site == "LAB-A"


def test_invalid_resolution_still_rejected():
    with pytest.raises(ValueError):
        DeviceDiscoveryCandidate(
            status="resolved",
            site="LAB-A",
        )
