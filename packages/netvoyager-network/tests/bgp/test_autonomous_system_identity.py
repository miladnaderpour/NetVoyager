"""Tests for deterministic AutonomousSystem UUIDv5 identities."""

from ipaddress import IPv4Network

from netvoyager_network.bgp.models import AutonomousSystem


def test_same_asn_has_same_identity():
    first = AutonomousSystem(asn=65520)
    second = AutonomousSystem(asn=65520)

    assert first.id == second.id
    assert first.id.version == 5


def test_different_asns_have_different_identities():
    first = AutonomousSystem(asn=65520)
    second = AutonomousSystem(asn=65534)

    assert first.id != second.id


def test_prefix_changes_do_not_change_identity():
    autonomous_system = AutonomousSystem(asn=65520)
    original_id = autonomous_system.id

    autonomous_system.add_prefix(
        IPv4Network("10.249.0.0/24")
    )

    assert autonomous_system.id == original_id

    autonomous_system.add_prefix(
        IPv4Network("10.249.1.0/24")
    )

    assert autonomous_system.id == original_id

    autonomous_system.remove_prefix(
        IPv4Network("10.249.0.0/24")
    )

    assert autonomous_system.id == original_id


def test_same_asn_with_different_prefixes_has_same_identity():
    first = AutonomousSystem(asn=65520)
    second = AutonomousSystem(asn=65520)

    first.add_prefix(
        IPv4Network("10.249.0.0/24")
    )

    second.add_prefix(
        IPv4Network("10.249.1.0/24")
    )

    assert first.id == second.id
    assert first.prefixes != second.prefixes
