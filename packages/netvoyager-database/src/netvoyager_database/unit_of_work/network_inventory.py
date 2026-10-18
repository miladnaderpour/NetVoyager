
"""Unit of Work for network inventory and discovery persistence."""

from __future__ import annotations

from netvoyager_database.repositories.devices.network_device import (
    SqlNetworkDeviceRepository,
)
from netvoyager_database.unit_of_work.base import BaseUnitOfWork


class NetworkInventoryUnitOfWork(BaseUnitOfWork):
    """Coordinate repositories involved in network inventory operations.

    All repositories share the same database session and transaction.

    Discovery persistence will be integrated when its concrete
    repository implementation is available.
    """

    def __init__(self, session_factory) -> None:
        """Initialize repository references without opening a session."""
        super().__init__(session_factory)
        self._devices: SqlNetworkDeviceRepository | None = None

    @property
    def devices(self) -> SqlNetworkDeviceRepository:
        """Return the canonical network-device repository."""
        self._require_active()

        if self._devices is None:
            raise RuntimeError(
                "The network-device repository is not initialized."
            )

        return self._devices

    def _initialize_repositories(self) -> None:
        """Initialize inventory repositories using the active session."""
        self._devices = SqlNetworkDeviceRepository(self.session)
