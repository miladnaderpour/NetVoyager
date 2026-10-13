"""Tests for canonical NetworkPrefix filtering."""

from ipaddress import IPv4Network

from netvoyager_network.ipam.filtering import filter_network_prefixes
from netvoyager_network.ipam.models import NetworkPrefix


def _prefix(
    value: str,
) -> NetworkPrefix:
    return NetworkPrefix(
        prefix=IPv4Network(
            value
        )
    )


def test_filter_network_prefixes_keeps_subnets() -> None:
    prefixes = (
        _prefix("10.131.0.0/24"),
        _prefix("10.132.0.0/24"),
        _prefix("192.168.1.0/24"),
    )

    result = filter_network_prefixes(
        prefixes,
        IPv4Network("10.0.0.0/8"),
    )

    assert tuple(
        prefix.prefix
        for prefix in result
    ) == (
        IPv4Network("10.131.0.0/24"),
        IPv4Network("10.132.0.0/24"),
    )