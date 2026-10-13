
"""Tests for Panorama site subnet selection."""

from ipaddress import IPv4Address, IPv4Network
from types import SimpleNamespace

from netvoyager_analysis.paloalto.subnets import (
    is_tunnel_interface,
    iter_site_subnet_candidates,
)
from netvoyager_paloalto.inventory.models import (
    InterfaceAddress,
    StaticRoute,
)


def connected(
    cidr: str,
    interface: str = "ethernet1/3",
    vr: str = "vpn_intern",
) -> InterfaceAddress:
    return InterfaceAddress(
        interface=interface,
        virtual_router=vr,
        ip_address=IPv4Address(cidr.split("/")[0]),
        prefix_length=int(cidr.split("/")[1]),
        configured_value=cidr,
        reported_prefix=None,
        record_index=0,
    )


def static(
    cidr: str,
    vr: str = "vpn_intern",
    interface: str | None = "ethernet1/3",
) -> StaticRoute:
    return StaticRoute(
        virtual_router=vr,
        route_name="Local_Route_2",
        destination=IPv4Network(cidr),
        interface=interface,
        next_hop="10.127.248.73",
        configured_value=cidr,
        reported_prefix=None,
        record_index=0,
    )


def firewall(*, connected_items=(), static_items=()):
    return SimpleNamespace(
        interface_addresses=connected_items,
        static_routes=static_items,
    )


def test_tunnel_interface_detection():
    assert is_tunnel_interface("tunnel.1")
    assert is_tunnel_interface(" TUNNEL.10 ")
    assert not is_tunnel_interface("ethernet1/3")
    assert not is_tunnel_interface("ae1.20")


def test_connected_and_static_selection():
    fw = firewall(
        connected_items=(
            connected("10.40.0.1/20"),
            connected("10.44.0.1/20", "tunnel.1"),
            connected("10.48.0.1/20", "ae1.20", "other_vr"),
        ),
        static_items=(
            static("10.160.216.0/23"),
            static("10.160.218.0/23", interface="tunnel.10"),
            static("10.160.220.0/23", vr="other_vr"),
            static("10.160.222.0/23", interface=None),
        ),
    )

    result = list(iter_site_subnet_candidates(fw))

    assert [
        (item.source, str(item.prefix))
        for item in result
    ] == [
        ("connected", "10.40.0.0/20"),
        ("connected", "10.48.0.0/20"),
        ("static", "10.160.216.0/23"),
    ]

    assert result[0].decision == "eligible"
    assert result[2].decision == "candidate"


def test_prefix_boundaries():
    fw = firewall(
        connected_items=(
            connected("10.0.0.1/12"),
            connected("10.32.0.1/13"),
            connected("10.44.0.1/19"),
            connected("10.44.8.1/20"),
            connected("10.44.8.1/31"),
            connected("10.44.8.1/32"),
        ),
        static_items=(
            static("10.0.0.0/12"),
            static("10.44.8.0/31"),
            static("10.44.8.1/32"),
        ),
    )

    result = list(iter_site_subnet_candidates(fw))

    assert [
        (item.source, item.prefix.prefixlen, item.decision)
        for item in result
    ] == [
        ("connected", 13, "candidate"),
        ("connected", 19, "candidate"),
        ("connected", 20, "eligible"),
        ("connected", 31, "eligible"),
        ("static", 31, "candidate"),
    ]
