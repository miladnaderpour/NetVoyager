"""Match IPv4 addresses to canonical network prefix objects."""

import logging
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Network

from .models import NetworkPrefix, NetworkPrefixMatchResult


logger = logging.getLogger(
    "netvoyager.network.ipam.matching"
)


PRIVATE_ADDRESS_SPACES = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)

OTHER_ADDRESS_SPACE = "other"


NetworkPrefixIndex = dict[
    str,
    dict[
        int,
        dict[
            IPv4Network,
            NetworkPrefix,
        ],
    ],
]


def find_most_specific_match(
    address: IPv4Address,
    prefixes: Iterable[NetworkPrefix],
    *,
    min_prefix_length: int | None = None,
    skip_broad_matches: bool = False,
) -> NetworkPrefixMatchResult:
    """Find the most-specific canonical prefix containing an IPv4 address.

    Consume the iterable once without modifying its NetworkPrefix objects.

    min_prefix_length is an inclusive minimum from 0 through 32. A best
    match with a shorter prefix length is marked as broader than expected.
    None disables the minimum-length check.

    When skip_broad_matches is False, a broad match remains in the result.
    When True, match becomes None while matched_prefix_length and
    is_broader_than_expected preserve information about the rejected match.

    Empty input or no matching prefix returns match=None,
    matched_prefix_length=None, and is_broader_than_expected=False.
    """
    _validate_min_prefix_length(
        min_prefix_length
    )

    best_match: NetworkPrefix | None = None
    best_length = -1

    for network_prefix in prefixes:
        if address not in network_prefix.prefix:
            continue

        prefix_length = (
            network_prefix.prefix.prefixlen
        )

        if prefix_length <= best_length:
            continue

        best_match = network_prefix
        best_length = prefix_length

    matched_prefix_length = (
        best_length
        if best_match is not None
        else None
    )

    is_broader_than_expected = (
        matched_prefix_length is not None
        and min_prefix_length is not None
        and matched_prefix_length < min_prefix_length
    )

    skip_match = (
        skip_broad_matches
        and is_broader_than_expected
    )

    result = NetworkPrefixMatchResult(
        match=(
            None
            if skip_match
            else best_match
        ),
        matched_prefix_length=(
            matched_prefix_length
        ),
        is_broader_than_expected=(
            is_broader_than_expected
        ),
    )

    logger.debug(
        "Most specific network prefix lookup completed",
        extra={
            "address": str(address),
            "matched_prefix": (
                str(result.match.prefix)
                if result.match is not None
                else None
            ),
            "matching_prefix_length": (
                result.matched_prefix_length
            ),
            "min_prefix_length": (
                min_prefix_length
            ),
            "is_broader_than_expected": (
                result.is_broader_than_expected
            ),
            "match_skipped": skip_match,
        },
    )

    return result


def build_prefix_index(
    prefixes: Iterable[NetworkPrefix],
) -> NetworkPrefixIndex:
    """Build an indexed lookup structure for canonical network prefixes.

    Prefixes fully contained within one of the RFC1918 address spaces are
    grouped under that address space. All other prefixes are placed in the
    ``other`` bucket.

    Within each address-space bucket, prefixes are grouped first by prefix
    length and then by exact IPv4 network.

    Canonical NetworkPrefix objects are expected to be unique by exact
    IPv4 network within the supplied analysis context.
    """
    index: NetworkPrefixIndex = {}

    prefix_count = 0

    for network_prefix in prefixes:
        network = network_prefix.prefix

        address_space = _network_address_space(
            network
        )

        lengths = index.setdefault(
            address_space,
            {},
        )

        networks = lengths.setdefault(
            network.prefixlen,
            {},
        )

        networks[
            network
        ] = network_prefix

        prefix_count += 1

    logger.debug(
        "Network prefix index built",
        extra={
            "prefix_count": prefix_count,
            "address_space_count": len(index),
        },
    )

    return index


def find_most_specific_match_indexed(
    address: IPv4Address,
    index: NetworkPrefixIndex,
    *,
    min_prefix_length: int | None = None,
    skip_broad_matches: bool = False,
) -> NetworkPrefixMatchResult:
    """Find the most-specific canonical prefix using a prebuilt index.

    Search from /32 toward /0 and stop at the first matching prefix.

    The matching RFC1918 bucket and the ``other`` bucket are both searched
    so that prefixes such as default routes and other broad networks remain
    detectable.

    When skip_broad_matches is True, a broad match is excluded while its
    prefix length and broader-than-expected status remain available.
    """
    _validate_min_prefix_length(
        min_prefix_length
    )

    address_space = _address_space(
        address
    )

    buckets = [
        address_space
    ]

    if address_space != OTHER_ADDRESS_SPACE:
        buckets.append(
            OTHER_ADDRESS_SPACE
        )

    for prefix_length in range(
        32,
        -1,
        -1,
    ):
        candidate = IPv4Network(
            (
                int(address),
                prefix_length,
            ),
            strict=False,
        )

        match = None

        for bucket in buckets:
            lengths = index.get(
                bucket
            )

            if lengths is None:
                continue

            networks = lengths.get(
                prefix_length
            )

            if networks is None:
                continue

            network_prefix = networks.get(
                candidate
            )

            if network_prefix is None:
                continue

            match = network_prefix
            break

        if match is None:
            continue

        is_broader_than_expected = (
            min_prefix_length is not None
            and prefix_length < min_prefix_length
        )

        skip_match = (
            skip_broad_matches
            and is_broader_than_expected
        )

        result = NetworkPrefixMatchResult(
            match=(
                None
                if skip_match
                else match
            ),
            matched_prefix_length=prefix_length,
            is_broader_than_expected=(
                is_broader_than_expected
            ),
        )

        logger.debug(
            "Indexed network prefix lookup completed",
            extra={
                "address": str(address),
                "address_space": address_space,
                "matched_prefix": (
                    str(match.prefix)
                ),
                "matching_prefix_length": (
                    result.matched_prefix_length
                ),
                "min_prefix_length": (
                    min_prefix_length
                ),
                "is_broader_than_expected": (
                    result.is_broader_than_expected
                ),
                "match_skipped": skip_match,
            },
        )

        return result

    return NetworkPrefixMatchResult()


def _address_space(
    address: IPv4Address,
) -> str:
    """Return the RFC1918 address-space bucket for an address."""
    for network in PRIVATE_ADDRESS_SPACES:
        if address in network:
            return str(
                network
            )

    return OTHER_ADDRESS_SPACE


def _network_address_space(
    network: IPv4Network,
) -> str:
    """Return the RFC1918 bucket containing an entire prefix."""
    for private_network in PRIVATE_ADDRESS_SPACES:
        if network.subnet_of(
            private_network
        ):
            return str(
                private_network
            )

    return OTHER_ADDRESS_SPACE


def _validate_min_prefix_length(
    min_prefix_length: int | None,
) -> None:
    """Validate the optional minimum prefix-length policy."""
    if min_prefix_length is None:
        return

    if (
        isinstance(
            min_prefix_length,
            bool,
        )
        or not isinstance(
            min_prefix_length,
            int,
        )
        or not 0 <= min_prefix_length <= 32
    ):
        raise ValueError(
            "min_prefix_length must be None or an integer "
            "from 0 through 32."
        )