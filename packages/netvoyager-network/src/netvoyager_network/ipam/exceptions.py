"""IPAM-specific exceptions using the shared NetVoyager error structure."""

from ipaddress import IPv4Network
from uuid import UUID

from netvoyager_core.exceptions import NetVoyagerError


class DuplicateNetworkPrefixIdError(NetVoyagerError):
    """Raised when a NetworkPrefix UUID already exists in a prefix store.

    UUIDs identify NetworkPrefix objects independently of their IPv4 network.
    Reusing an existing UUID would make object identity ambiguous.
    """

    def __init__(
        self,
        *,
        prefix_id: UUID,
    ) -> None:
        """Describe the duplicate NetworkPrefix UUID."""
        self.prefix_id = prefix_id

        super().__init__(
            code="ipam.duplicate_network_prefix_id",
            message=(
                f"Network prefix ID {prefix_id} already exists."
            ),
            details={
                "prefix_id": str(prefix_id),
            },
        )


class DuplicateNetworkPrefixError(NetVoyagerError):
    """Raised when an exact IPv4 network already exists in a prefix store.

    Exact equality requires the same network address and prefix length.

    Overlapping, containing, or contained networks are not considered
    duplicates by this exception.
    """

    def __init__(
        self,
        *,
        prefix: IPv4Network,
        existing_id: UUID,
    ) -> None:
        """Describe the duplicate IPv4 network and existing object UUID."""
        self.prefix = prefix
        self.existing_id = existing_id

        super().__init__(
            code="ipam.duplicate_network_prefix",
            message=(
                f"Network prefix {prefix} already exists "
                f"with ID {existing_id}."
            ),
            details={
                "prefix": str(prefix),
                "existing_id": str(existing_id),
            },
        )