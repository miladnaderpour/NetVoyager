
from dataclasses import dataclass
from ipaddress import IPv4Address


@dataclass(frozen=True, slots=True)
class NetworkDevice:
    """A network device independent of its inventory source."""

    name: str

    role: str | None = None
    site: str | None = None
    description: str | None = None

    primary_IPv4: IPv4Address | None = None
    management_ip: IPv4Address | None = None
    host_name: str | None = None

    virtual_chassis: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    status: str | None = None
    asset_tag: str | None = None
