## netwoyager-network/netvoyager_network/bgp/matching.py
"""Match an IPv4 address to its most specific supplied BGP prefix records."""

import logging
from collections.abc import Iterable
from ipaddress import IPv4Address

from .models import AsPrefix, AsPrefixMatchResult


logger = logging.getLogger("netvoyager.network.bgp.matching")


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
    the broader-than-expected flag remain available. This option has no
    effect when min_prefix_length is None.

    Empty input or no matching prefix returns an empty matches tuple,
    matched_prefix_length=None, and is_broader_than_expected=False.

    Matching considers only the supplied records. Excluding records
    beforehand, including routes with unknown origin ASNs, can change
    the best match. This function does not select an ASN, resolve
    ambiguous associations, or perform BGP best-path selection.

    Raise ValueError if min_prefix_length is not None or an integer
    from 0 through 32. Boolean values are not accepted as prefix lengths.
    """
    if min_prefix_length is not None:
        if (
            isinstance(min_prefix_length, bool)
            or not isinstance(min_prefix_length, int)
            or not 0 <= min_prefix_length <= 32
        ):
            raise ValueError(
                "min_prefix_length must be None or an integer "
                "from 0 through 32."
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

    matched_prefix_length = best_length if matches else None

    is_broader_than_expected = (
        matched_prefix_length is not None
        and min_prefix_length is not None
        and matched_prefix_length < min_prefix_length
    )

    skip_matches = skip_broad_matches and is_broader_than_expected

    result = AsPrefixMatchResult(
        matches=() if skip_matches else tuple(matches),
        matched_prefix_length=matched_prefix_length,
        is_broader_than_expected=is_broader_than_expected,
    )

    logger.debug(
        "Most specific BGP prefix lookup completed",
        extra={
            "match_count": len(result.matches),
            "matching_prefix_length": result.matched_prefix_length,
            "min_prefix_length": min_prefix_length,
            "is_broader_than_expected": result.is_broader_than_expected,
            "skipped_match_count": len(matches) if skip_matches else 0,
        },
    )

    return result