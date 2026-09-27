"""Match an IPv4 address to its most specific BGP routes."""

import logging
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Network

from .grouping import RouteWithAsPath
from .models import PrefixAsMatch


logger = logging.getLogger("netvoyager.network.bgp.matching")


def find_most_specific_matches(
    address: IPv4Address,
    routes: Iterable[RouteWithAsPath],
    scope: IPv4Network | None = None,
) -> tuple[PrefixAsMatch, ...]:
    """Return every route at the longest matching prefix length."""
    best_length = -1
    matches: set[PrefixAsMatch] = set()

    for route in routes:
        prefix = route.prefix

        if scope is not None and not prefix.subnet_of(scope):
            continue
        if address not in prefix:
            continue

        if prefix.prefixlen > best_length:
            best_length = prefix.prefixlen
            matches.clear()

        if prefix.prefixlen == best_length:
            matches.add(
                PrefixAsMatch(
                    prefix=prefix,
                    origin_as=route.as_path[-1] if route.as_path else None,
                )
            )

    result = tuple(
        sorted(
            matches,
            key=lambda match: (
                int(match.prefix.network_address),
                match.prefix.prefixlen,
                -1 if match.origin_as is None else match.origin_as,
            ),
        )
    )

    logger.debug(
        "Most specific BGP prefix lookup completed",
        extra={
            "match_count": len(result),
            "matching_prefix_length": best_length if result else None,
        },
    )
    return result