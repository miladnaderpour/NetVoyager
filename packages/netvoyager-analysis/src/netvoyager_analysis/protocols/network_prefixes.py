
"""Persistence-independent contract for canonical IPAM identities."""

from typing import Protocol
from uuid import UUID

from netvoyager_network.ipam.address_space import AddressSpace
from netvoyager_network.ipam.models import NetworkPrefix


class NetworkPrefixRepositoryProtocol(Protocol):
    """Access canonical address spaces and accepted network prefixes."""

    def get_address_space(
        self,
        space_id: UUID,
    ) -> AddressSpace | None:
        """Retrieve an address space by identity."""
        ...

    def add_address_space(
        self,
        space: AddressSpace,
    ) -> None:
        """Insert an established address space."""
        ...

    def get_prefix(
        self,
        prefix_id: UUID,
    ) -> NetworkPrefix | None:
        """Retrieve a canonical network prefix by identity."""
        ...

    def find_prefix(
        self,
        prefix: str,
        address_space_id: UUID,
    ) -> NetworkPrefix | None:
        """Find an exact normalized CIDR within an address space."""
        ...

    def add_prefix(
        self,
        prefix: NetworkPrefix,
    ) -> None:
        """Insert an already-authorized canonical network prefix."""
        ...
