
"""Tests for independent, normalized network-prefix source observations."""

from ipaddress import IPv4Network, IPv6Network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_analysis.sources.models import Source, SourceDataset


def test_dataset_preserves_independent_observations() -> None:
    first = PrefixObservation(
        local_ref="route-1",
        prefix=IPv4Network("192.0.2.1/24", strict=False),
        observation_kind="bgp_route",
        routing_context="vrf-example",
        local_device_ref="router-1",
    )
    second = PrefixObservation(
        local_ref="route-2",
        prefix=IPv4Network("192.0.2.0/24"),
        observation_kind="static_route",
    )
    dataset = SourceDataset(
        source=Source(name="Synthetic collection", source_type="cli_text"),
        network_prefixes=(first, second),
    )

    assert len(dataset.network_prefixes) == 2
    assert first.prefix == second.prefix
    assert first.observation_id != second.observation_id
    assert first.address_space_id is None
    assert first.routing_context == "vrf-example"
    assert dataset.devices == ()


def test_explicit_address_space_and_ipv6() -> None:
    address_space_id = uuid4()
    observation = PrefixObservation(
        local_ref="interface-1",
        prefix=IPv6Network("2001:db8::1/64", strict=False),
        observation_kind="interface_network",
        address_space_id=address_space_id,
    )
    assert observation.prefix == IPv6Network("2001:db8::/64")
    assert observation.address_space_id == address_space_id


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"local_ref": "  "}, ValueError),
        ({"prefix": "192.0.2.0/24"}, TypeError),
        ({"observation_kind": ""}, ValueError),
        ({"address_space_id": "global"}, TypeError),
        ({"local_device_ref": ""}, ValueError),
        ({"routing_context": 15}, TypeError),
    ],
)
def test_invalid_observations_rejected(changes, error) -> None:
    kwargs = {
        "local_ref": "prefix-1",
        "prefix": IPv4Network("192.0.2.0/24"),
        "observation_kind": "inventory",
    }
    kwargs.update(changes)
    with pytest.raises(error):
        PrefixObservation(**kwargs)
