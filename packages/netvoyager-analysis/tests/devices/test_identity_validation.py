"""Regression tests for evidence-independent physical identity validation."""
from ipaddress import IPv4Address

from netvoyager_network.device.models import NetworkDevice
from netvoyager_analysis.devices.discovery.models import DeviceDiscoveryCandidate
from netvoyager_analysis.devices.candidate_matching import (
    IdentityTarget, compare_identity_targets, match_device_candidates,
)
from netvoyager_analysis.devices.identity_validation import IdentityValidator
from netvoyager_analysis.devices.matching_rules import SourceRef

EXCEL = SourceRef("excel_inventory", "device_inventory")
PAN = SourceRef("paloalto_panorama", "managed_device_inventory")


def test_matching_serial_pair_verifies():
    a = DeviceDiscoveryCandidate(serial_number="ABC")
    b = DeviceDiscoveryCandidate(serial_number="ABC")
    match = compare_identity_targets(IdentityTarget(a), IdentityTarget(b))
    assert IdentityValidator().validate_match(match).verified


def test_weak_hostname_match_unresolved():
    a = DeviceDiscoveryCandidate(host_name="FW")
    b = DeviceDiscoveryCandidate(host_name="FW")
    match = compare_identity_targets(IdentityTarget(a), IdentityTarget(b))
    assert IdentityValidator().validate_match(match).status == "unresolved"


def test_new_canonical_serial_eligible():
    target = IdentityTarget(DeviceDiscoveryCandidate(serial_number="SER"), PAN)
    result = IdentityValidator().validate_canonical_identity(target, canonical_devices=())
    assert result.verified and result.matched_device_id is None


def test_existing_canonical_reused():
    device = NetworkDevice(name="FW", serial_number="SER")
    target = IdentityTarget(DeviceDiscoveryCandidate(serial_number="SER"), PAN)
    result = IdentityValidator().validate_canonical_identity(target, canonical_devices=(device,))
    assert result.matched_device_id == device.device_id


def test_duplicate_canonical_ids_conflict():
    devices = (NetworkDevice(name="FW1", serial_number="SER"), NetworkDevice(name="FW2", serial_number="SER"))
    target = IdentityTarget(DeviceDiscoveryCandidate(serial_number="SER"), PAN)
    assert IdentityValidator().validate_canonical_identity(target, canonical_devices=devices).status == "conflict"


def test_duplicate_reference_to_one_canonical_not_conflict():
    device = NetworkDevice(name="FW", serial_number="SER")
    target = IdentityTarget(DeviceDiscoveryCandidate(serial_number="SER"), PAN)
    assert IdentityValidator().validate_canonical_identity(target, canonical_devices=(device, device)).verified


def test_missing_serial_unresolved():
    target = IdentityTarget(DeviceDiscoveryCandidate(host_name="FW"), PAN)
    assert IdentityValidator().validate_canonical_identity(target, canonical_devices=()).status == "unresolved"


def test_excel_to_panorama_canonical_reconciliation():
    fw = NetworkDevice(name="FW", serial_number="0012345")
    target = IdentityTarget(DeviceDiscoveryCandidate(serial_number="12345"), EXCEL)
    result = IdentityValidator().validate_canonical_identity(target, canonical_devices=(IdentityTarget(fw, PAN),))
    assert result.verified and result.matched_device_id == fw.device_id


def test_multiple_excel_candidates_not_automatic_conflict():
    a = IdentityTarget(DeviceDiscoveryCandidate(serial_number="12345"), EXCEL)
    b = IdentityTarget(DeviceDiscoveryCandidate(serial_number="12345"), EXCEL)
    pan = IdentityTarget(DeviceDiscoveryCandidate(serial_number="0012345"), PAN)
    matches = match_device_candidates(pan, (a, b))
    result = IdentityValidator().validate_candidate_matches(matches)
    assert len(result) == 2 and all(item.verified for item in result)
