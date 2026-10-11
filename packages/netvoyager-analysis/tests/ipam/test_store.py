"""Tests for the IPAM network prefix store."""

from ipaddress import IPv4Network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.store import NetworkPrefixStore
from netvoyager_network.ipam.exceptions import (
    DuplicateNetworkPrefixError,
    DuplicateNetworkPrefixIdError,
)
from netvoyager_network.ipam.models import NetworkPrefix


def test_add_and_get_network_prefix() -> None:
    """Add a network prefix and retrieve it by UUID."""
    store = NetworkPrefixStore()

    network_prefix = NetworkPrefix(
        prefix=IPv4Network("10.131.0.0/24"),
    )

    store.add(network_prefix)

    assert store.get(network_prefix.id) is network_prefix


def test_find_exact_returns_matching_network_prefix() -> None:
    """Return the canonical object for an exact IPv4 network."""
    store = NetworkPrefixStore()

    network_prefix = NetworkPrefix(
        prefix=IPv4Network("10.131.0.0/24"),
    )
    store.add(network_prefix)

    result = store.find_exact(
        IPv4Network("10.131.0.0/24"),
    )

    assert result is network_prefix


def test_find_exact_does_not_match_overlapping_network() -> None:
    """Do not treat overlapping IPv4 networks as exact matches."""
    store = NetworkPrefixStore()

    store.add(
        NetworkPrefix(
            prefix=IPv4Network("10.131.0.0/24"),
        )
    )

    result = store.find_exact(
        IPv4Network("10.131.0.0/25"),
    )

    assert result is None


def test_get_or_create_creates_network_prefix_when_absent() -> None:
    """Create and return a network prefix when no exact match exists."""
    store = NetworkPrefixStore()

    network_prefix, created = store.get_or_create(
        IPv4Network("10.131.0.0/24"),
    )

    assert created is True
    assert network_prefix.prefix == IPv4Network("10.131.0.0/24")
    assert store.get(network_prefix.id) is network_prefix
    assert len(store) == 1


def test_get_or_create_reuses_existing_network_prefix() -> None:
    """Reuse the canonical object when the exact network already exists."""
    store = NetworkPrefixStore()

    first, first_created = store.get_or_create(
        IPv4Network("10.131.0.0/24"),
    )
    second, second_created = store.get_or_create(
        IPv4Network("10.131.0.0/24"),
    )

    assert first_created is True
    assert second_created is False
    assert second is first
    assert len(store) == 1


def test_add_rejects_duplicate_network_prefix_id() -> None:
    """Reject a second object that reuses an existing NetworkPrefix UUID."""
    store = NetworkPrefixStore()
    prefix_id = uuid4()

    first = NetworkPrefix(
        id=prefix_id,
        prefix=IPv4Network("10.131.0.0/24"),
    )
    second = NetworkPrefix(
        id=prefix_id,
        prefix=IPv4Network("10.132.0.0/24"),
    )

    store.add(first)

    with pytest.raises(DuplicateNetworkPrefixIdError):
        store.add(second)


def test_add_rejects_duplicate_exact_network() -> None:
    """Reject a different object representing an existing exact network."""
    store = NetworkPrefixStore()

    first = NetworkPrefix(
        prefix=IPv4Network("10.131.0.0/24"),
    )
    second = NetworkPrefix(
        prefix=IPv4Network("10.131.0.0/24"),
    )

    store.add(first)

    with pytest.raises(DuplicateNetworkPrefixError):
        store.add(second)


def test_values_preserve_insertion_order() -> None:
    """Return stored network prefixes in insertion order."""
    store = NetworkPrefixStore()

    first = NetworkPrefix(
        prefix=IPv4Network("10.131.0.0/24"),
    )
    second = NetworkPrefix(
        prefix=IPv4Network("10.132.0.0/24"),
    )

    store.add(first)
    store.add(second)

    assert store.values() == (
        first,
        second,
    )