"""Store canonical network prefix objects for IPAM analysis.

The store owns NetworkPrefix objects and provides lookup by UUID and exact
IPv4 prefix. Exact-prefix lookup is used to prevent duplicate canonical
NetworkPrefix objects within the current analysis context.
"""

from ipaddress import IPv4Network
from uuid import UUID

from netvoyager_network.ipam.exceptions import (
    DuplicateNetworkPrefixError,
    DuplicateNetworkPrefixIdError,
)
from netvoyager_network.ipam.models import NetworkPrefix


class NetworkPrefixStore:
    """Store and retrieve canonical IPv4 network prefix objects.

    Network prefixes are indexed by both UUID and exact IPv4 network.

    Within one store, an exact IPv4 network maps to one canonical
    NetworkPrefix object. Repeated observations of the same network therefore
    reuse the existing object instead of creating another object.

    This first version does not distinguish identical prefixes in different
    routing contexts. Routing-context awareness can be introduced later by
    extending the exact-prefix lookup key.
    """

    def __init__(self) -> None:
        """Initialize an empty network prefix store."""
        self._by_id: dict[UUID, NetworkPrefix] = {}
        self._by_prefix: dict[IPv4Network, UUID] = {}

    def add(self, network_prefix: NetworkPrefix) -> None:
        """Add a network prefix to the store.

        The prefix is indexed by UUID and exact IPv4 network.

        Raise DuplicateNetworkPrefixIdError if the UUID already exists.
        Raise DuplicateNetworkPrefixError if the exact IPv4 network is already
        associated with another NetworkPrefix object.
        """
        if network_prefix.id in self._by_id:
            raise DuplicateNetworkPrefixIdError(
                prefix_id=network_prefix.id,
            )

        existing_id = self._by_prefix.get(network_prefix.prefix)

        if existing_id is not None:
            raise DuplicateNetworkPrefixError(
                prefix=network_prefix.prefix,
                existing_id=existing_id,
            )

        self._by_id[network_prefix.id] = network_prefix
        self._by_prefix[network_prefix.prefix] = network_prefix.id

    def get(self, prefix_id: UUID) -> NetworkPrefix | None:
        """Return a network prefix by UUID if it exists."""
        return self._by_id.get(prefix_id)

    def find_exact(
        self,
        prefix: IPv4Network,
    ) -> NetworkPrefix | None:
        """Return the canonical object for an exact IPv4 network.

        Matching requires both the network address and prefix length to be
        identical. Overlapping, containing, or contained networks are not
        considered matches.
        """
        prefix_id = self._by_prefix.get(prefix)

        if prefix_id is None:
            return None

        return self._by_id[prefix_id]

    def get_or_create(
        self,
        prefix: IPv4Network,
    ) -> tuple[NetworkPrefix, bool]:
        """Return the canonical network prefix, creating it when absent.

        Return a tuple containing the NetworkPrefix object and a boolean
        indicating whether a new object was created.

        Exact IPv4 network equality determines reuse.
        """
        existing = self.find_exact(prefix)

        if existing is not None:
            return existing, False

        network_prefix = NetworkPrefix(prefix=prefix)
        self.add(network_prefix)

        return network_prefix, True

    def values(self) -> tuple[NetworkPrefix, ...]:
        """Return all stored network prefixes in insertion order."""
        return tuple(self._by_id.values())

    def __len__(self) -> int:
        """Return the number of stored network prefixes."""
        return len(self._by_id)