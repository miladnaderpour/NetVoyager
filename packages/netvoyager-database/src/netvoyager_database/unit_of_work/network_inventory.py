
"""Unit of Work for network inventory and intelligence persistence.

Device, evidence, and finding repositories share one SQLAlchemy session
and transaction. Discovery persistence is integrated separately when
its concrete repository implementation is available.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from netvoyager_database.exceptions import TransactionError
from netvoyager_database.repositories.devices.network_device import (
    SqlNetworkDeviceRepository,
)
from netvoyager_database.repositories.evidence import (
    SqlEvidenceRepository,
)
from netvoyager_database.repositories.findings import (
    SqlFindingRepository,
)
from netvoyager_database.unit_of_work.base import BaseUnitOfWork


class NetworkInventoryUnitOfWork(BaseUnitOfWork):
    """Coordinate inventory and intelligence repository transactions.

    All repositories use the same active database session.

    Changes are committed explicitly. Uncommitted work is rolled back
    by BaseUnitOfWork when the transaction scope exits.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
    ) -> None:
        """Initialize repository references without opening a session."""
        super().__init__(session_factory)

        self._devices: SqlNetworkDeviceRepository | None = None
        self._evidence: SqlEvidenceRepository | None = None
        self._findings: SqlFindingRepository | None = None

    @property
    def devices(self) -> SqlNetworkDeviceRepository:
        """Return the canonical network-device repository."""
        self._require_active()

        if self._devices is None:
            raise TransactionError(
                code="storage.repository_not_initialized",
                message="The network-device repository is not initialized.",
            )

        return self._devices

    @property
    def evidence(self) -> SqlEvidenceRepository:
        """Return the evidence provenance repository."""
        self._require_active()

        if self._evidence is None:
            raise TransactionError(
                code="storage.repository_not_initialized",
                message="The evidence repository is not initialized.",
            )

        return self._evidence

    @property
    def findings(self) -> SqlFindingRepository:
        """Return the analysis-finding repository."""
        self._require_active()

        if self._findings is None:
            raise TransactionError(
                code="storage.repository_not_initialized",
                message="The finding repository is not initialized.",
            )

        return self._findings

    def _initialize_repositories(self) -> None:
        """Initialize repositories using the active database session."""
        session = self.session

        self._devices = SqlNetworkDeviceRepository(session)
        self._evidence = SqlEvidenceRepository(session)
        self._findings = SqlFindingRepository(session)
