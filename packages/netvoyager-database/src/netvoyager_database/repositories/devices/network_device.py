
"""SQLAlchemy repository for canonical network devices.

The repository implements domain-oriented persistence operations.
Identity validation, reconciliation, and policy decisions remain
outside the database layer.

Transaction commit and rollback belong to the Unit of Work.
"""

from __future__ import annotations

from ipaddress import IPv4Address
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from netvoyager_core.logging import get_logger
from netvoyager_network.device.models import NetworkDevice
from netvoyager_database.exceptions import (
    RepositoryConflictError,
    RepositoryNotFoundError,
)

from netvoyager_database.entities.devices.network_device import (
    NetworkDeviceEntity,
)
from netvoyager_database.mappers.devices.network_device import (
    to_domain,
    to_entity,
)


logger = get_logger(__name__)


class SqlNetworkDeviceRepository:
    """Persist and retrieve canonical network devices using SQLAlchemy.

    The repository operates within a caller-owned Session.

    Query methods return detached domain objects. Changes must be
    persisted explicitly through add() or save().

    Write operations flush pending SQL but never commit or roll back
    the caller's transaction.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the repository with a transaction-scoped session."""
        self._session = session

    def get_by_id(
        self,
        device_id: UUID,
    ) -> NetworkDevice | None:
        """Return a canonical device by its UUID, if present."""
        entity = self._session.get(NetworkDeviceEntity, device_id)

        return to_domain(entity) if entity is not None else None

    def find_by_name(
        self,
        name: str,
    ) -> NetworkDevice | None:
        """Return a canonical device by its unique name, if present."""
        statement = select(NetworkDeviceEntity).where(
            NetworkDeviceEntity.name == name
        )

        entity = self._session.scalar(statement)

        return to_domain(entity) if entity is not None else None

    def find_by_serial(
        self,
        serial_number: str,
    ) -> tuple[NetworkDevice, ...]:
        """Return all devices matching the exact stored serial number."""
        statement = (
            select(NetworkDeviceEntity)
            .where(NetworkDeviceEntity.serial_number == serial_number)
            .order_by(NetworkDeviceEntity.name)
        )

        return self._find_many(statement)

    def find_by_management_ip(
        self,
        management_ip: IPv4Address,
    ) -> tuple[NetworkDevice, ...]:
        """Return all devices matching the management IPv4 address."""
        statement = (
            select(NetworkDeviceEntity)
            .where(NetworkDeviceEntity.management_ip == str(management_ip))
            .order_by(NetworkDeviceEntity.name)
        )

        return self._find_many(statement)

    def find_by_asset_tag(
        self,
        asset_tag: str,
    ) -> tuple[NetworkDevice, ...]:
        """Return all devices matching the exact stored asset tag."""
        statement = (
            select(NetworkDeviceEntity)
            .where(NetworkDeviceEntity.asset_tag == asset_tag)
            .order_by(NetworkDeviceEntity.name)
        )

        return self._find_many(statement)

    def add(
        self,
        device: NetworkDevice,
    ) -> None:
        """Insert a new canonical device without replacing existing data.

        An existing canonical identity raises RepositoryConflictError.

        Flush detects database constraint violations before the caller
        attempts to commit the Unit of Work.
        """
        entity = to_entity(device)

        self._session.add(entity)

        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code="storage.device_already_exists",
                message="Cannot insert a conflicting canonical device.",
                details={
                    "device_id": str(device.device_id),
                    "name": device.name,
                },
            ) from exc

        logger.debug(
            "Canonical device inserted",
            extra={
                "device_id": str(device.device_id),
                "device_name": device.name,
            },
        )

    def save(
        self,
        device: NetworkDevice,
    ) -> None:
        """Persist the current state of an existing canonical device.

        The canonical identity must already exist. This operation
        does not perform an implicit insert or authorize lifecycle
        changes such as hardware replacement.
        """
        entity = self._session.get(
            NetworkDeviceEntity,
            device.device_id,
        )

        if entity is None:
            raise RepositoryNotFoundError(
                code="storage.device_not_found",
                message="Cannot update a canonical device that does not exist.",
                details={
                    "device_id": str(device.device_id),
                    "name": device.name,
                },
            )

        if entity.name != device.name:
            raise RepositoryConflictError(
                code="storage.device_identity_conflict",
                message="Stored canonical device identity does not match.",
                details={
                    "device_id": str(device.device_id),
                    "stored_name": entity.name,
                    "provided_name": device.name,
                },
            )

        updated = to_entity(device)

        entity.role = updated.role
        entity.site = updated.site
        entity.description = updated.description
        entity.primary_ipv4 = updated.primary_ipv4
        entity.management_ip = updated.management_ip
        entity.host_name = updated.host_name
        entity.virtual_chassis = updated.virtual_chassis
        entity.manufacturer = updated.manufacturer
        entity.model = updated.model
        entity.serial_number = updated.serial_number
        entity.status = updated.status
        entity.asset_tag = updated.asset_tag
        entity.software_version = updated.software_version
        entity.integration_metadata = updated.integration_metadata


        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code="storage.device_update_conflict",
                message="Cannot persist the canonical device state.",
                details={
                    "device_id": str(device.device_id),
                    "name": device.name,
                },
            ) from exc

        logger.debug(
            "Canonical device state persisted",
            extra={
                "device_id": str(device.device_id),
                "name": device.name,
                "state_id": str(device.state_id),
            },
        )

    def _find_many(
        self,
        statement,
    ) -> tuple[NetworkDevice, ...]:
        """Return reconstructed domain devices for a SQL query."""
        entities = self._session.scalars(statement).all()

        return tuple(to_domain(entity) for entity in entities)
