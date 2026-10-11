"""Filter canonical network prefixes by IPv4 address range."""

from collections.abc import Iterable
from ipaddress import IPv4Network

from .models import NetworkPrefix


def filter_network_prefixes(
    prefixes: Iterable[NetworkPrefix],
    within: IPv4Network,
) -> tuple[NetworkPrefix, ...]:
    """Keep canonical prefixes fully contained within ``within``.

    Preserve input encounter order. A prefix that only overlaps the boundary
    is excluded. The supplied NetworkPrefix objects are not modified.
    """
    return tuple(
        network_prefix
        for network_prefix in prefixes
        if network_prefix.prefix.subnet_of(
            within
        )
    )