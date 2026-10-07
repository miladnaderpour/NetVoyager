"""Match IPv4 addresses to the most specific supplied BGP prefix records."""

import logging
from collections import defaultdict
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Network

from .models import AsPrefix, AsPrefixMatchResult


logger = logging.getLogger("netvoyager.network.bgp.matching")


PRIVATE_ADDRESS_SPACES = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)

OTHER_ADDRESS_SPACE = "other"


PrefixIndex = dict[
    str,
    dict[
        int,
        dict[
            IPv4Network,
            tuple[AsPrefix, ...],
        ],
    ],
]


def find_most_specific_matches(
    address: IPv4Address,
    records: Iterable[AsPrefix],
    *,
    min_prefix_length: int | None = None,
    skip_broad_matches: bool = False,
) -> AsPrefixMatchResult:
    """Find the best prefix matches and optionally assess their specificity.

    Return all records at the longest prefix containing the address.
    Preserve input encounter order, duplicate occurrences, ASNs, and AS
    paths. Consume the iterable once without modifying its records.

    min_prefix_length is an inclusive minimum from 0 through 32. A best
    match with a shorter prefix length is marked as broader than expected.
    None disables the minimum-length check.

    When skip_broad_matches is False, broad matches remain in the result.
    When True, they are excluded, but their matched prefix length and
    the broader-than-expected flag remain available.

    Empty input or no matching prefix returns an empty matches tuple,
    matched_prefix_length=None, and is_broader_than_expected=False.
    """
    _validate_min_prefix_length(
        min_prefix_length
    )

    best_length = -1
    matches: list[AsPrefix] = []

    for record in records:
        if not record.contains(address):
            continue

        prefix_length = record.prefix.prefixlen

        if prefix_length > best_length:
            best_length = prefix_length
            matches.clear()

        if prefix_length == best_length:
            matches.append(record)

    matched_prefix_length = (
        best_length
        if matches
        else None
    )

    is_broader_than_expected = (
        matched_prefix_length is not None
        and min_prefix_length is not None
        and matched_prefix_length < min_prefix_length
    )

    skip_matches = (
        skip_broad_matches
        and is_broader_than_expected
    )

    result = AsPrefixMatchResult(
        matches=(
            ()
            if skip_matches
            else tuple(matches)
        ),
        matched_prefix_length=matched_prefix_length,
        is_broader_than_expected=is_broader_than_expected,
    )

    logger.debug(
        "Most specific BGP prefix lookup completed",
        extra={
            "match_count": len(result.matches),
            "matching_prefix_length": (
                result.matched_prefix_length
            ),
            "min_prefix_length": min_prefix_length,
            "is_broader_than_expected": (
                result.is_broader_than_expected
            ),
            "skipped_match_count": (
                len(matches)
                if skip_matches
                else 0
            ),
        },
    )

    return result


def build_prefix_index(
    records: Iterable[AsPrefix],
) -> PrefixIndex:
    """Build an indexed lookup structure for BGP prefix records.

    Prefixes fully contained within one of the RFC1918 address spaces are
    grouped under that address space. All other prefixes are placed in the
    ``other`` bucket.

    Within each address-space bucket, records are grouped first by prefix
    length and then by exact IPv4 network.

    Repeated AsPrefix observations for the same network are preserved in
    input encounter order.
    """
    grouped: dict[
        str,
        dict[
            int,
            dict[
                IPv4Network,
                list[AsPrefix],
            ],
        ],
    ] = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(list)
        )
    )

    record_count = 0

    for record in records:
        address_space = _network_address_space(
            record.prefix
        )

        grouped[
            address_space
        ][
            record.prefix.prefixlen
        ][
            record.prefix
        ].append(record)

        record_count += 1

    index: PrefixIndex = {}

    for address_space, lengths in grouped.items():
        index[address_space] = {}

        for prefix_length, networks in lengths.items():
            index[address_space][prefix_length] = {
                network: tuple(network_records)
                for network, network_records in networks.items()
            }

    logger.debug(
        "BGP prefix index built",
        extra={
            "record_count": record_count,
            "address_space_count": len(index),
        },
    )

    return index


def find_most_specific_matches_indexed(
    address: IPv4Address,
    index: PrefixIndex,
    *,
    min_prefix_length: int | None = None,
    skip_broad_matches: bool = False,
) -> AsPrefixMatchResult:
    """Find the most specific BGP prefix using a prebuilt prefix index.

    Search from /32 toward /0 and stop at the first prefix length with
    matching records.

    All AsPrefix observations for the matching exact network are returned.
    Less-specific supernets are not returned once a more-specific match
    exists.

    The matching RFC1918 bucket and the ``other`` bucket are both searched
    so that broad prefixes such as a default route remain detectable.
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

        matches: list[AsPrefix] = []

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

            network_matches = networks.get(
                candidate
            )

            if network_matches is None:
                continue

            matches.extend(
                network_matches
            )

        if not matches:
            continue

        is_broader_than_expected = (
            min_prefix_length is not None
            and prefix_length < min_prefix_length
        )

        skip_matches = (
            skip_broad_matches
            and is_broader_than_expected
        )

        result = AsPrefixMatchResult(
            matches=(
                ()
                if skip_matches
                else tuple(matches)
            ),
            matched_prefix_length=prefix_length,
            is_broader_than_expected=(
                is_broader_than_expected
            ),
        )

        logger.debug(
            "Indexed BGP prefix lookup completed",
            extra={
                "address": str(address),
                "address_space": address_space,
                "match_count": len(result.matches),
                "matching_prefix_length": (
                    result.matched_prefix_length
                ),
                "min_prefix_length": min_prefix_length,
                "is_broader_than_expected": (
                    result.is_broader_than_expected
                ),
                "skipped_match_count": (
                    len(matches)
                    if skip_matches
                    else 0
                ),
            },
        )

        return result

    return AsPrefixMatchResult()


def _address_space(
    address: IPv4Address,
) -> str:
    """Return the RFC1918 address-space bucket for an address."""
    for network in PRIVATE_ADDRESS_SPACES:
        if address in network:
            return str(network)

    return OTHER_ADDRESS_SPACE


def _network_address_space(
    network: IPv4Network,
) -> str:
    """Return the RFC1918 bucket containing an entire prefix."""
    for private_network in PRIVATE_ADDRESS_SPACES:
        if network.subnet_of(
            private_network
        ):
            return str(private_network)

    return OTHER_ADDRESS_SPACE


def _validate_min_prefix_length(
    min_prefix_length: int | None,
) -> None:
    """Validate the optional minimum prefix-length policy."""
    if min_prefix_length is None:
        return

    if (
        isinstance(min_prefix_length, bool)
        or not isinstance(min_prefix_length, int)
        or not 0 <= min_prefix_length <= 32
    ):
        raise ValueError(
            "min_prefix_length must be None or an integer "
            "from 0 through 32."
        )