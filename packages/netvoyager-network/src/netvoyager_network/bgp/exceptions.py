#NetVoyager_network/bgp/exceptions.py
"""BGP-specific exceptions using the shared NetVoyager error structure."""

from ipaddress import IPv4Network

from netvoyager_core.exceptions import NetVoyagerError


class DuplicatePrefixError(NetVoyagerError):
    """Raised when adding a prefix already associated with an AS.

    A duplicate means the exact same network address and prefix length.
    Overlapping networks with different prefix lengths are not duplicates.

    The exception exposes ASN and prefix as typed attributes, while details
    contains JSON-compatible values for structured reporting.
    """

    def __init__(self, *, asn: int, prefix: IPv4Network) -> None:
        """Describe the duplicate without changing the AS prefix collection."""
        self.asn = asn
        self.prefix = prefix

        super().__init__(
            code="bgp.duplicate_prefix",
            message=f"Prefix {prefix} already exists in AS {asn}.",
            details={
                "asn": asn,
                "prefix": str(prefix),
            },
        )