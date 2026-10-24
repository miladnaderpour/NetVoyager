
"""Convert canonical IPAM domain objects to and from SQL entities."""

from ipaddress import ip_network

from netvoyager_core.exceptions import NetVoyagerInvariantError
from netvoyager_network.ipam.address_space import AddressSpace
from netvoyager_network.ipam.models import NetworkPrefix

from netvoyager_database.entities.ipam.canonical import (
    AddressSpaceEntity,
    NetworkPrefixEntity,
)


def address_space_to_entity(
    space: AddressSpace,
) -> AddressSpaceEntity:
    """Convert a domain address space to a persistence entity."""
    return AddressSpaceEntity(
        id=space.id,
        name=space.name,
    )


def address_space_to_domain(
    entity: AddressSpaceEntity,
) -> AddressSpace:
    """Reconstruct an address space preserving its stable identity."""
    return AddressSpace(
        id=entity.id,
        name=entity.name,
    )


def network_prefix_to_entity(
    prefix: NetworkPrefix,
) -> NetworkPrefixEntity:
    """Convert a canonical prefix to its persistence representation."""
    return NetworkPrefixEntity(
        id=prefix.id,
        address_space_id=prefix.address_space_id,
        prefix=prefix.prefix.with_prefixlen,
    )


def network_prefix_to_domain(
    entity: NetworkPrefixEntity,
) -> NetworkPrefix:
    """Reconstruct and verify the deterministic canonical identity."""
    prefix = NetworkPrefix(
        prefix=ip_network(entity.prefix, strict=True),
        address_space_id=entity.address_space_id,
    )

    if prefix.id != entity.id:
        raise NetVoyagerInvariantError(
            code="database.prefix_identity_mismatch",
            message="Stored canonical prefix identity is inconsistent.",
            details={
                "stored_id": str(entity.id),
                "expected_id": str(prefix.id),
                "prefix": entity.prefix,
            },
        )

    return prefix
