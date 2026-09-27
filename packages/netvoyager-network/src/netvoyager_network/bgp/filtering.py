"""Filter grouped BGP prefixes by address range."""

from collections.abc import Iterable
from ipaddress import IPv4Network

from .models import AsPrefixes


def filter_as_prefixes(
    groups: Iterable[AsPrefixes],
    scope: IPv4Network,
) -> tuple[AsPrefixes, ...]:
    """Keep prefixes fully contained within scope."""
    return tuple(
        AsPrefixes(
            asn=group.asn,
            prefixes=tuple(
                prefix
                for prefix in group.prefixes
                if prefix.subnet_of(scope)
            ),
        )
        for group in groups
        if any(prefix.subnet_of(scope) for prefix in group.prefixes)
    )