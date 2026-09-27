"""Group BGP prefixes by their observed origin ASN."""

import logging
from collections.abc import Iterable
from ipaddress import IPv4Network
from typing import Protocol

from .models import AsPrefixes


logger = logging.getLogger("netvoyager.network.bgp.grouping")


class RouteWithAsPath(Protocol):
    prefix: IPv4Network
    as_path: tuple[int, ...]


def group_prefixes_by_origin_as(
    routes: Iterable[RouteWithAsPath],
) -> tuple[AsPrefixes, ...]:
    """Group route prefixes by the rightmost ASN in their AS path."""
    prefixes_by_as: dict[int, set[IPv4Network]] = {}
    route_count = 0
    local_route_count = 0

    for route in routes:
        route_count += 1

        if not route.as_path:
            local_route_count += 1
            continue

        origin_as = route.as_path[-1]
        prefixes_by_as.setdefault(origin_as, set()).add(route.prefix)

    groups = tuple(
        AsPrefixes(
            asn=asn,
            prefixes=tuple(
                sorted(
                    prefixes,
                    key=lambda prefix: (
                        int(prefix.network_address),
                        prefix.prefixlen,
                    ),
                )
            ),
        )
        for asn, prefixes in sorted(prefixes_by_as.items())
    )

    logger.info(
        "BGP prefixes grouped by origin ASN",
        extra={
            "route_count": route_count,
            "as_count": len(groups),
            "local_routes_skipped": local_route_count,
        },
    )
    return groups