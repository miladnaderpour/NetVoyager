"""Models for firewall inventory collected through Panorama."""

from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Literal


CollectionState = Literal["pending", "success", "partial", "failed"]
IssueSeverity = Literal["info", "warning", "error"]


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
    """Configured static route; does not imply operational status."""

    virtual_router: str
    route_name: str | None
    destination: IPv4Network | None
    interface: str | None
    next_hop: str | None
    configured_value: str
    reported_prefix: str | None
    record_index: int


@dataclass(frozen=True, slots=True)
class BgpPeer:
    """Configured BGP peer; does not imply an established session."""

    name: str
    enabled: bool | None
    peer_as: int | None
    raw_peer_as: str | None

    # Strings preserve addresses, FQDNs, and address-object references.
    peer_address_ip: str | None
    peer_address_fqdn: str | None
    local_interface: str | None
    local_address: str | None
    address_family: str | None
    enable_mp_bgp: bool | None
    raw_xml: str | None


@dataclass(frozen=True, slots=True)
class BgpPeerGroup:
    name: str
    enabled: bool | None
    type: str | None
    peers: tuple[BgpPeer, ...]
    raw_xml: str | None


@dataclass(frozen=True, slots=True)
class BgpRule:
    """Ordered policy or redistribution rule.

    Detailed matches and actions are preserved in raw_xml.
    """

    name: str
    enabled: bool | None
    raw_xml: str | None


@dataclass(frozen=True, slots=True)
class RedistributionProfile:
    name: str
    raw_xml: str | None


@dataclass(frozen=True, slots=True)
class BgpConfiguration:
    present: bool | None
    enabled: bool | None
    local_as: int | None
    raw_local_as: str | None
    router_id: IPv4Address | None
    raw_router_id: str | None
    install_route: bool | None
    reject_default_route: bool | None
    allow_redistribute_default_route: bool | None

    peer_groups: tuple[BgpPeerGroup, ...]
    import_rules: tuple[BgpRule, ...]
    export_rules: tuple[BgpRule, ...]
    redistribution_rules: tuple[BgpRule, ...]
    raw_xml: str | None


@dataclass(frozen=True, slots=True)
class VirtualRouterConfiguration:
    name: str
    interfaces: tuple[str, ...]
    bgp: BgpConfiguration | None
    redistribution_profiles: tuple[RedistributionProfile, ...]


@dataclass(frozen=True, slots=True)
class CollectionStatus:
    """Collector-reported status, separate from parsing issues."""

    subnets: CollectionState | None
    management: CollectionState | None
    ha: CollectionState | None
    virtual_routers: CollectionState | None = None


@dataclass(frozen=True, slots=True)
class FirewallInventory:
    serial: str
    hostname: str
    management: ManagementInfo | None
    ha: HAInfo | None
    interface_addresses: tuple[InterfaceAddress, ...]
    static_routes: tuple[StaticRoute, ...]
    collection_status: CollectionStatus

    # None means unavailable/not collected; () means an empty collection.
    virtual_routers: tuple[VirtualRouterConfiguration, ...] | None = None


@dataclass(frozen=True, slots=True)
class PanoramaImportIssue:
    severity: IssueSeverity
    path: str
    reason: str
    firewall_serial: str | None = None
    raw_value_json: str | None = None


@dataclass(frozen=True, slots=True)
class CollectionFailure:
    serial: str
    hostname: str | None
    section: str
    error: str


@dataclass(frozen=True, slots=True)
class PanoramaInventoryResult:
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