
"""Address-space-aware canonical prefix identity tests."""

from dataclasses import replace
from ipaddress import IPv4Network, IPv6Network
from uuid import UUID, uuid4, uuid5

import pytest

from netvoyager_network.ipam.address_space import (
    ADDRESS_SPACE_NAMESPACE,
    GLOBAL_ADDRESS_SPACE,
    GLOBAL_ADDRESS_SPACE_ID,
    AddressSpace,
)
from netvoyager_network.ipam.models import (
    NETWORK_PREFIX_NAMESPACE,
    NetworkPrefix,
)


def test_global_address_space_is_deterministic():
    assert GLOBAL_ADDRESS_SPACE.name == "global"
    assert GLOBAL_ADDRESS_SPACE.id == GLOBAL_ADDRESS_SPACE_ID
    assert GLOBAL_ADDRESS_SPACE_ID == uuid5(
        ADDRESS_SPACE_NAMESPACE,
        "address-space:global",
    )


def test_address_space_rename_does_not_change_identity():
    space = AddressSpace(id=uuid4(), name="LAB-A")
    renamed = replace(space, name="LAB-RENAMED")
    assert renamed.id == space.id


def test_address_space_requires_valid_identity_and_name():
    with pytest.raises(TypeError):
        AddressSpace(id="not-a-uuid", name="LAB")

    with pytest.raises(ValueError):
        AddressSpace(id=uuid4(), name="  ")


def test_default_network_prefix_uses_global_address_space():
    result = NetworkPrefix(
        prefix=IPv4Network("192.0.2.0/24"),
    )

    assert result.address_space_id == GLOBAL_ADDRESS_SPACE_ID
    assert result.id == uuid5(
        NETWORK_PREFIX_NAMESPACE,
        f"network-prefix:{GLOBAL_ADDRESS_SPACE_ID}:192.0.2.0/24",
    )
    assert result.id.version == 5


def test_identical_prefix_in_same_space_has_same_identity():
    space_id = uuid4()

    first = NetworkPrefix(
        prefix=IPv4Network("192.0.2.1/24", strict=False),
        address_space_id=space_id,
    )
    second = NetworkPrefix(
        prefix=IPv4Network("192.0.2.0/24"),
        address_space_id=space_id,
    )

    assert first.id == second.id
    assert isinstance(first.id, UUID)


def test_identical_prefix_in_different_spaces_has_different_identity():
    network = IPv4Network("192.0.2.0/24")

    first = NetworkPrefix(
        prefix=network,
        address_space_id=uuid4(),
    )
    second = NetworkPrefix(
        prefix=network,
        address_space_id=uuid4(),
    )

    assert first.id != second.id


def test_different_prefixes_in_same_space_have_different_identity():
    first = NetworkPrefix(
        prefix=IPv4Network("192.0.2.0/24"),
    )
    second = NetworkPrefix(
        prefix=IPv4Network("192.0.2.0/23"),
    )

    assert first.id != second.id


def test_ipv6_identity_is_deterministic_and_address_space_aware():
    space_id = uuid4()

    first = NetworkPrefix(
        prefix=IPv6Network("2001:db8::1/64", strict=False),
        address_space_id=space_id,
    )
    second = NetworkPrefix(
        prefix=IPv6Network("2001:db8::/64"),
        address_space_id=space_id,
    )
    global_prefix = NetworkPrefix(
        prefix=IPv6Network("2001:db8::/64"),
    )

    assert first.id == second.id
    assert first.id != global_prefix.id


def test_prefix_requires_typed_network_and_address_space_id():
    with pytest.raises(TypeError):
        NetworkPrefix(prefix="192.0.2.0/24")

    with pytest.raises(TypeError):
        NetworkPrefix(
            prefix=IPv4Network("192.0.2.0/24"),
            address_space_id="global",
        )
 