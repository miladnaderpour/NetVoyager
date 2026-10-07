"""Protocols for device observations consumed by analysis."""

from ipaddress import IPv4Address
from typing import Protocol


class DeviceIdentityObservation(Protocol):
    """Minimum device identity information used for reconciliation.

    Implementations do not need to inherit from this protocol. They only
    need to expose compatible read-only attributes.
    """

    @property
    def name(self) -> str | None:
        """Return the observed device name, if available."""
        ...

    @property
    def host_name(self) -> str | None:
        """Return the observed configured hostname, if available."""
        ...

    @property
    def management_ip(self) -> IPv4Address | None:
        """Return the observed management IPv4 address, if available."""
        ...

    @property
    def serial_number(self) -> str | None:
        """Return the observed serial number, if available."""
        ...


class DeviceObservation(DeviceIdentityObservation, Protocol):
    """Structural interface for an observed network device.

    Device observations describe information reported by an external source
    such as an inventory file, vendor API, LLDP, or CDP.

    An observation is not itself a NetworkDevice. It represents source data
    that analysis can use to identify, create, or update a device and to
    produce supporting evidence.

    All attributes may be unavailable because different sources expose
    different amounts of device information.
    """

    @property
    def site(self) -> str | None:
        """Return the observed site identifier or name, if available."""
        ...

    @property
    def role(self) -> str | None:
        """Return the observed device role, if available."""
        ...

    @property
    def primary_IPv4(self) -> IPv4Address | None:
        """Return the observed primary IPv4 address, if available."""
        ...

    @property
    def manufacturer(self) -> str | None:
        """Return the observed manufacturer, if available."""
        ...

    @property
    def model(self) -> str | None:
        """Return the observed hardware model, if available."""
        ...

    @property
    def asset_tag(self) -> str | None:
        """Return the observed asset tag, if available."""
        ...

    @property
    def software_version(self) -> str | None:
        """Return the observed software version, if available."""
        ...

    @property
    def status(self) -> str | None:
        """Return the observed device status, if available."""
        ...

    @property
    def line_number(self) -> int | None:
        """Return the source record or line number, if available."""
        ...

    @property
    def raw_line(self) -> str | None:
        """Return a human-readable representation of the source record."""
        ...