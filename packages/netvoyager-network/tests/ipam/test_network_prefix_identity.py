
from ipaddress import IPv4Network
from uuid import UUID

from netvoyager_network.ipam.models import NetworkPrefix


def test_same_prefix_has_same_identity():
    first = NetworkPrefix(
        prefix=IPv4Network("10.165.0.0/24"),
    )

    second = NetworkPrefix(
        prefix=IPv4Network("10.165.0.0/24"),
    )

    assert first.id == second.id
    assert first.id.version == 5


def test_different_prefix_has_different_identity():
    first = NetworkPrefix(
        prefix=IPv4Network("10.165.0.0/24"),
    )

    second = NetworkPrefix(
        prefix=IPv4Network("10.165.0.0/23"),
    )

    assert first.id != second.id


def test_identity_is_deterministic():
    prefix = NetworkPrefix(
        prefix=IPv4Network("10.165.0.0/24"),
    )

    assert isinstance(prefix.id, UUID)
    assert prefix.id == NetworkPrefix(
        prefix=IPv4Network("10.165.0.0/24"),
    ).id
