
"""Storage-independent contract for coordinated repository transactions."""

from types import TracebackType
from typing import Protocol, Self

from .devices import NetworkDeviceRepositoryProtocol
from .discovery import DeviceDiscoveryRepositoryProtocol
from .evidence import EvidenceRepositoryProtocol
from .findings import FindingRepositoryProtocol


class UnitOfWorkProtocol(Protocol):
    """Coordinate repository operations within one transaction scope.

    Repositories exposed by a Unit of Work participate in the same
    consistency boundary.

    Changes require an explicit commit. Uncommitted changes must
    be rolled back when the context exits.

    Implementations manage transaction resources without exposing
    backend-specific sessions to application services.
    """

    @property
    def devices(self) -> NetworkDeviceRepositoryProtocol:
        """Return the canonical network-device repository."""
        ...

    @property
    def discovery(self) -> DeviceDiscoveryRepositoryProtocol:
        """Return the device-discovery repository."""
        ...

    @property
    def evidence(self) -> EvidenceRepositoryProtocol:
        """Return the evidence provenance repository."""
        ...

    @property
    def findings(self) -> FindingRepositoryProtocol:
        """Return the analysis-finding repository."""
        ...

    def __enter__(self) -> Self:
        """Enter a coordinated transaction scope."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the scope and roll back any uncommitted changes."""
        ...

    def commit(self) -> None:
        """Commit all changes within the transaction atomically."""
        ...

    def rollback(self) -> None:
        """Discard uncommitted changes in the transaction."""
        ...
