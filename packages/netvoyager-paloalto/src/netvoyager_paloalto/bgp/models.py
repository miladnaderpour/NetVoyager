"""Models for parsed Palo Alto BGP local RIB output."""

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Literal

CollectionState = Literal["pending", "success", "partial", "failed"]




@dataclass(frozen=True, slots=True)
class BgpRoute:
    prefix: IPv4Network
    next_hop: IPv4Address | None
    peer: str
    as_path: tuple[int, ...]
    marker: Literal["*"] | None  # empty tuple when the column is blank
    line_number: int
    raw_line: str


@dataclass(frozen=True, slots=True)
class UnparsedLine:
    line_number: int
    reason: str
    raw_line: str


@dataclass(frozen=True, slots=True)
class BgpRibResult:
    virtual_router: str
    virtual_router_id: int | None
    routes: tuple[BgpRoute, ...]
    total_routes_shown: int | None
    unparsed_lines: tuple[UnparsedLine, ...]


@dataclass(frozen=True, slots=True)
class BgpRibDump:
    routers: tuple[BgpRibResult, ...]
    unparsed_lines: tuple[UnparsedLine, ...] = ()


@dataclass(frozen=True, slots=True)
class ManagementInfo:
    """Dedicated management interface addressing."""

    ip_address: IPv4Address | None
    prefix_length: int | None
    default_gateway: IPv4Address | None
    is_dhcp: bool | None

    raw_ip_address: str | None
    raw_netmask: str | None
    raw_default_gateway: str | None

    collected_at_utc: datetime | None

    @property
    def interface_address(self) -> IPv4Interface | None:
        if self.ip_address is None or self.prefix_length is None:
            return None

        return IPv4Interface(f"{self.ip_address}/{self.prefix_length}")

    @property
    def network(self) -> IPv4Network | None:
        address = self.interface_address
        return address.network if address is not None else None


@dataclass(frozen=True, slots=True)
class HAInfo:
    """Reported HA state at collection time."""

    enabled: bool | None
    mode: str | None
    group_id: str | None

    local_state: str | None
    peer_serial: str | None
    peer_state: str | None
    peer_connection: str | None

    config_sync: str | None
    sync_enabled: bool | None

    collected_at_utc: datetime | None
    raw_xml: str | None


@dataclass(frozen=True, slots=True)
class InterfaceAddress:
    """One configured IPv4 address on a virtual-router interface."""

    interface: str
    virtual_router: str

    ip_address: IPv4Address | None
    prefix_length: int | None

    configured_value: str
    reported_prefix: str | None

    # Original position in the firewall's JSON subnets array.
    record_index: int

    @property
    def interface_address(self) -> IPv4Interface | None:
        if self.ip_address is None or self.prefix_length is None:
            return None

        return IPv4Interface(f"{self.ip_address}/{self.prefix_length}")

    @property
    def network(self) -> IPv4Network | None:
        address = self.interface_address
        return address.network if address is not None else None


@dataclass(frozen=True, slots=True)
class StaticRoute:
    """One configured static route, without implying operational status."""

    virtual_router: str
    route_name: str | None

    destination: IPv4Network | None
    interface: str | None
    next_hop: str | None

    configured_value: str
    reported_prefix: str | None
    record_index: int


@dataclass(frozen=True, slots=True)
class CollectionStatus:
    """Collector-reported status; distinct from Python parsing issues."""

    subnets: CollectionState | None
    management: CollectionState | None
    ha: CollectionState | None


@dataclass(frozen=True, slots=True)
class FirewallInventory:
    """Collected evidence for one physical or virtual firewall."""

    serial: str
    hostname: str

    management: ManagementInfo | None
    ha: HAInfo | None

    interface_addresses: tuple[InterfaceAddress, ...]
    static_routes: tuple[StaticRoute, ...]

    collection_status: CollectionStatus


@dataclass(frozen=True, slots=True)
class PanoramaImportIssue:
    """A parsing problem or normalization that needs visibility."""

    severity: Literal["info", "warning", "error"]
    path: str
    reason: str
    firewall_serial: str | None = None

    # JSON text preserving a problematic value or rejected record.
    raw_value_json: str | None = None


@dataclass(frozen=True, slots=True)
class CollectionFailure:
    """An error reported by the PowerShell collector."""

    serial: str
    hostname: str | None
    section: str
    error: str


@dataclass(frozen=True, slots=True)
class PanoramaInventoryResult:
    """Parsed Panorama inventory and its collection provenance."""

    schema_version: str
    panorama: str

    collection_started_at_utc: datetime
    collected_at_utc: datetime

    panorama_connected: int
    selected_connected: int
    selected_not_connected: tuple[str, ...]

    firewalls: tuple[FirewallInventory, ...]
    collection_failures: tuple[CollectionFailure, ...]
    issues: tuple[PanoramaImportIssue, ...]