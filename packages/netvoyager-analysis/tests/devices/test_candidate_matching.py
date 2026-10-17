"""Regression tests for object-based candidate/canonical matching."""
from ipaddress import IPv4Address
from uuid import uuid4

from netvoyager_network.device.models import NetworkDevice
from netvoyager_analysis.devices.discovery.models import DeviceDiscoveryCandidate
from netvoyager_analysis.devices.candidate_matching import (
    IdentityTarget, compare_identity_targets, match_device_candidates,
)
from netvoyager_analysis.devices.matching_rules import SourceRef

EXCEL = SourceRef("excel_inventory", "device_inventory")
PAN = SourceRef("paloalto_panorama", "managed_device_inventory")


def candidate(serial=None, hostname=None, ip=None):
    return DeviceDiscoveryCandidate(serial_number=serial, host_name=hostname, management_ip=ip)


def test_exact_serial_candidate_pair():
    a, b = candidate("ABC1"), candidate(" abc1 ")
    result = compare_identity_targets(IdentityTarget(a), IdentityTarget(b))
    assert result.has_serial_match
    assert result.signals[0].method == "exact_serial"


def test_excel_panorama_leading_zeros():
    a, b = candidate("123456789"), candidate("00123456789")
    result = compare_identity_targets(IdentityTarget(a, EXCEL), IdentityTarget(b, PAN))
    assert result is not None
    assert result.signals[0].method == "numeric_leading_zero_loss"


def test_leading_zeros_without_source_context_do_not_match():
    a, b = candidate("123456789"), candidate("00123456789")
    assert compare_identity_targets(IdentityTarget(a), IdentityTarget(b)) is None


def test_name_not_required_for_serial_matching():
    a, b = candidate("SERIAL"), candidate("SERIAL")
    assert compare_identity_targets(IdentityTarget(a), IdentityTarget(b)).has_serial_match


def test_hostname_alone_is_weak():
    a, b = candidate(hostname="FW"), candidate(hostname="fw")
    result = compare_identity_targets(IdentityTarget(a), IdentityTarget(b))
    assert result is not None and not result.has_serial_match
    assert result.signals[0].method == "hostname"


def test_shared_ip_is_weak():
    ip = IPv4Address("10.1.1.1")
    result = compare_identity_targets(IdentityTarget(candidate(ip=ip)), IdentityTarget(candidate(ip=ip)))
    assert result is not None and not result.has_serial_match


def test_different_serials_veto_same_hostname():
    a, b = candidate("AAA", "same"), candidate("BBB", "same")
    assert compare_identity_targets(IdentityTarget(a), IdentityTarget(b)) is None


def test_no_self_match():
    a = candidate("AAA")
    assert compare_identity_targets(IdentityTarget(a), IdentityTarget(a)) is None


def test_candidates_can_match_canonical():
    a = candidate("ABC")
    b = NetworkDevice(name="canonical", serial_number="ABC")
    result = compare_identity_targets(IdentityTarget(a), IdentityTarget(b))
    assert result is not None and result.has_serial_match


def test_canonical_can_match_canonical():
    a = NetworkDevice(name="one", serial_number="ABC")
    b = NetworkDevice(name="two", serial_number="ABC")
    result = compare_identity_targets(IdentityTarget(a), IdentityTarget(b))
    assert result is not None and result.has_serial_match


def test_all_candidates_returned_without_mutation():
    a, b, c = candidate("ABC"), candidate("ABC"), candidate("ABC")
    result = match_device_candidates(IdentityTarget(a), [IdentityTarget(b), IdentityTarget(c), IdentityTarget(b)])
    assert len(result.matches) == 2
    assert a.status == b.status == c.status == "candidate"
