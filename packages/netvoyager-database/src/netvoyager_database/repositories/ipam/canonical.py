
"""SQL persistence for canonical address spaces and network prefixes."""

from __future__ import annotations

from ipaddress import ip_network
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from netvoyager_database.entities.ipam.canonical import (
    AddressSpaceEntity,
    NetworkPrefixEntity,
)
from netvoyager_database.exceptions import RepositoryConflictError
from netvoyager_database.mappers.ipam.canonical import (
    address_space_to_domain,
    address_space_to_entity,
    network_prefix_to_domain,
    network_prefix_to_entity,
)
from netvoyager_network.ipam.address_space import AddressSpace
from netvoyager_network.ipam.models import NetworkPrefix


class SqlNetworkPrefixRepository:
    """Store canonical IPAM identities in a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _flush(self, code: str, message: str) -> None:
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code=code,
                message=message,
            ) from exc

    def get_address_space(
        self,
        space_id: UUID,
    ) -> AddressSpace | None:
        entity = self._session.get(AddressSpaceEntity, space_id)
        return (
            address_space_to_domain(entity)
            if entity is not None
            else None
        )

    def add_address_space(self, space: AddressSpace) -> None:
        self._session.add(address_space_to_entity(space))
        self._flush(
            "storage.address_space_conflict",
            "Cannot insert conflicting address space.",
        )

    def get_prefix(
        self,
        prefix_id: UUID,
    ) -> NetworkPrefix | None:
        entity = self._session.get(NetworkPrefixEntity, prefix_id)
        return (
            network_prefix_to_domain(entity)
            if entity is not None
            else None
        )

    def find_prefix(
        self,
        prefix: str,
        address_space_id: UUID,
    ) -> NetworkPrefix | None:
        normalized = ip_network(
            prefix,
            strict=False,
        ).with_prefixlen

        statement = select(NetworkPrefixEntity).where(
            NetworkPrefixEntity.prefix == normalized,
            NetworkPrefixEntity.address_space_id == address_space_id,
        )

        entity = self._session.scalar(statement)

        return (
            network_prefix_to_domain(entity)
            if entity is not None
            else None
        )

    def add_prefix(self, prefix: NetworkPrefix) -> None:
        if self.get_address_space(prefix.address_space_id) is None:
            raise RepositoryConflictError(
                code="storage.address_space_missing",
                message="Canonical prefix address space does not exist.",
            )

        self._session.add(network_prefix_to_entity(prefix))
        self._flush(
            "storage.network_prefix_conflict",
            "Cannot insert conflicting canonical network prefix.",
        )
