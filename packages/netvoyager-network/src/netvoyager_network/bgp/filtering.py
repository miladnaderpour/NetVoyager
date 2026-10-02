# netwoyager-network/netvoyager_network/bgp/filtering.py
"""Filter BGP prefix records by address range."""

from collections.abc import Iterable
from ipaddress import IPv4Network

from .models import AsPrefix


def filter_as_prefixes(
    records: Iterable[AsPrefix],
    within: IPv4Network,
) -> tuple[AsPrefix, ...]:
    """Keep records whose IPv4 prefix is fully contained in ``within``.

    Preserve record order, repeated prefixes, and AS paths. A prefix that only
    overlaps the boundary is excluded. The input records are not modified.
    """
    return tuple(record for record in records if record.prefix.subnet_of(within))
