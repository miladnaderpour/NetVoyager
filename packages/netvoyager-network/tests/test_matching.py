"""Tests for canonical NetworkPrefix matching."""

from ipaddress import IPv4Address, IPv4Network

import pytest

from netvoyager_network.ipam.matching import (
    build_prefix_index,
    find_most_specific_match,
    find_most_specific_match_indexed,
)
from netvoyager_network.ipam.models import NetworkPrefix


def _prefix(
    value: str,
) -> NetworkPrefix:
    return NetworkPrefix(
        prefix=IPv4Network(
            value
        )
    )


def test_find_most_specific_match_returns_longest_prefix() -> None:
    prefixes = (
        _prefix("10.0.0.0/8"),
        _prefix("10.131.0.0/16"),
        _prefix("10.131.0.0/24"),
    )

    result = find_most_specific_match(
        IPv4Address("10.131.0.50"),
        prefixes,
    )

    assert result.match is not None
    assert result.match.prefix == IPv4Network(
        "10.131.0.0/24"
    )
    assert result.matched_prefix_length == 24
    assert result.is_broader_than_expected is False


def test_find_most_specific_match_returns_none_when_no_match() -> None:
    prefixes = (
        _prefix("10.131.0.0/24"),
    )

    result = find_most_specific_match(
        IPv4Address("10.132.0.1"),
        prefixes,
    )

    assert result.match is None
    assert result.matched_prefix_length is None
    assert result.is_broader_than_expected is False


def test_find_most_specific_match_flags_broad_match() -> None:
    prefixes = (
        _prefix("10.0.0.0/8"),
    )

    result = find_most_specific_match(
        IPv4Address("10.131.0.1"),
        prefixes,
        min_prefix_length=16,
    )

    assert result.match is not None
    assert result.matched_prefix_length == 8
    assert result.is_broader_than_expected is True


def test_find_most_specific_match_can_skip_broad_match() -> None:
    prefixes = (
        _prefix("10.0.0.0/8"),
    )

    result = find_most_specific_match(
        IPv4Address("10.131.0.1"),
        prefixes,
        min_prefix_length=16,
        skip_broad_matches=True,
    )

    assert result.match is None
    assert result.matched_prefix_length == 8
    assert result.is_broader_than_expected is True


def test_indexed_match_returns_longest_prefix() -> None:
    prefixes = (
        _prefix("10.0.0.0/8"),
        _prefix("10.131.0.0/16"),
        _prefix("10.131.0.0/24"),
        _prefix("10.131.0.50/32"),
    )

    index = build_prefix_index(
        prefixes
    )

    result = find_most_specific_match_indexed(
        IPv4Address("10.131.0.50"),
        index,
    )

    assert result.match is not None
    assert result.match.prefix == IPv4Network(
        "10.131.0.50/32"
    )
    assert result.matched_prefix_length == 32


def test_indexed_match_finds_other_address_space_prefix() -> None:
    prefixes = (
        _prefix("0.0.0.0/0"),
    )

    index = build_prefix_index(
        prefixes
    )

    result = find_most_specific_match_indexed(
        IPv4Address("10.131.0.50"),
        index,
    )

    assert result.match is not None
    assert result.match.prefix == IPv4Network(
        "0.0.0.0/0"
    )


def test_indexed_match_preserves_canonical_object() -> None:
    network_prefix = _prefix(
        "10.131.0.0/24"
    )

    index = build_prefix_index(
        (network_prefix,)
    )

    result = find_most_specific_match_indexed(
        IPv4Address("10.131.0.50"),
        index,
    )

    assert result.match is network_prefix


@pytest.mark.parametrize(
    "value",
    (
        -1,
        33,
        True,
        False,
        16.0,
        "16",
    ),
)
def test_invalid_min_prefix_length_raises(
    value: object,
) -> None:
    with pytest.raises(
        ValueError
    ):
        find_most_specific_match(
            IPv4Address("10.131.0.1"),
            (),
            min_prefix_length=value,  # type: ignore[arg-type]
        )