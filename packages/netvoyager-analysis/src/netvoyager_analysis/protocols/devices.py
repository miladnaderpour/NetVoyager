
"""Storage-independent repository contract for canonical network devices."""

from ipaddress import IPv4Address
from typing import Protocol
from uuid import UUID

from netvoyager_network.device.models import NetworkDevice


class NetworkDeviceRepositoryProtocol(Protocol):
    """Provide domain-oriented access to canonical network devices.

    Implementations may use in-memory indexes, database queries,
    or other storage mechanisms.

    Repository operations do not validate physical identity,
    authorize reconciliation, or apply lifecycle decisions.
    """

    def get_by_id(
        self,
        device_id: UUID,
    ) -> NetworkDevice | None:
        """Return a canonical device by its UUID, if present."""
        ...

    def find_by_name(
        self,
        name: str,
    ) -> NetworkDevice | None:
        """Return a canonical device by its unique name, if present."""
        ...

    def find_by_serial(
        self,
        serial_number: str,
    ) -> tuple[NetworkDevice, ...]:
        """Return all devices with the exact stored serial number."""
        ...

    def find_by_management_ip(
        self,
        management_ip: IPv4Address,
    ) -> tuple[NetworkDevice, ...]:
        """Return all devices with the given management IPv4 address."""
        ...

    def find_by_asset_tag(
        self,
        asset_tag: str,
    ) -> tuple[NetworkDevice, ...]:
        """Return all devices with the given asset tag."""
        ...

    def add(
        self,
        device: NetworkDevice,
    ) -> None:
        """Register a new canonical device without replacing an existing one."""
        ...

    def save(
        self,
        device: NetworkDevice,
    ) -> None:
        """Persist changes to an existing canonical device."""
        ...
