
"""Shared, framework-independent IPAM domain models.

Importers normalize and validate input before constructing domain objects.
An unknown observation address space must remain unresolved; the default
below is for deliberately constructed canonical prefixes only.
"""

from dataclasses import dataclass, field
from ipaddress import IPv4Network, IPv6Network
from uuid import UUID, uuid5

from .address_space import GLOBAL_ADDRESS_SPACE_ID

NETWORK_PREFIX_NAMESPACE = UUID(
    "b9a7da8a-5b4f-4f05-8a71-163056b8d682"
)


@dataclass(frozen=True, slots=True)
class NetworkPrefix:
    """An accepted prefix uniquely identified within one address space.

    Site ownership, routing context and ASN attribution remain separate.
    """

    prefix: IPv4Network | IPv6Network
    address_space_id: UUID = GLOBAL_ADDRESS_SPACE_ID
    id: UUID = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.prefix, (IPv4Network, IPv6Network)):
            raise TypeError(
                "NetworkPrefix.prefix must be an IPv4Network or IPv6Network"
            )

        if not isinstance(self.address_space_id, UUID):
            raise TypeError(
                "NetworkPrefix.address_space_id must be a UUID"
            )

        object.__setattr__(
            self,
            "id",
            uuid5(
                NETWORK_PREFIX_NAMESPACE,
                f"network-prefix:{self.address_space_id}:"
                f"{self.prefix.with_prefixlen}",
            ),
        )


@dataclass(frozen=True, slots=True)
class NetworkPrefixMatchResult:
    """Best canonical prefix match for an address.

    The existing matcher currently supports IPv4 only. Its address-space
    filtering will be revised in the matching milestone.
    """

    match: NetworkPrefix | None = None
    matched_prefix_length: int | None = None
    is_broader_than_expected: bool = False
