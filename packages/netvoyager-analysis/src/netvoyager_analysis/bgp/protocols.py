#netwoyager-analysis\src\netvoyager_analysis\evidence\protocols.py
"""Structural contracts for BGP processing and evidence creation.

Vendor models satisfy these protocols through attributes or properties.
Explicit inheritance is not required. Protocols support static type
checking; they do not validate or convert runtime values.
"""

from ipaddress import IPv4Address, IPv4Network
from typing import Protocol


class BgpRouteObservation(Protocol):
    """A parsed IPv4 BGP route available for processing and evidence.

    Device identity and routing context are supplied separately.

    AS paths contain an ordered ASN sequence with repetitions preserved.
    An empty tuple means an observed empty path; None means unavailable.
    Producers must not flatten unordered AS sets into ordered sequences.

    Source line information may be None for structured sources without
    text lines. Read-only properties support mutable and frozen vendor
    models without requiring writable attributes.
    """

    @property
    def prefix(self) -> IPv4Network:
        """Return the observed IPv4 network."""
        ...

    @property
    def next_hop(self) -> IPv4Address | None:
        """Return the next-hop address, or None when unavailable."""
        ...

    @property
    def peer(self) -> str | None:
        """Return the source peer label, or None when unavailable.

        The label may describe a local route rather than a remote neighbor.
        """
        ...

    @property
    def as_path(self) -> tuple[int, ...] | None:
        """Return the ordered AS path, an empty path, or None."""
        ...

    @property
    def line_number(self) -> int | None:
        """Return the one-based source line number when available."""
        ...

    @property
    def raw_line(self) -> str | None:
        """Return the original source line when available."""
        ...