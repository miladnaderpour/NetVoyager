"""Adapters for Palo Alto Panorama observations."""

from dataclasses import dataclass
from ipaddress import IPv4Address

from netvoyager_paloalto.inventory.models import FirewallInventory


@dataclass(frozen=True, slots=True)
class PanoramaDeviceIdentity:
    """Generic device identity derived from Panorama firewall inventory."""

    name: str | None
    host_name: str | None
    management_ip: IPv4Address | None
    serial_number: str | None

    firewall: FirewallInventory


def adapt_panorama_firewall(
    firewall: FirewallInventory,
) -> PanoramaDeviceIdentity:
    """Adapt a Panorama firewall into a generic device identity observation."""
    return PanoramaDeviceIdentity(
        name=firewall.hostname,
        host_name=firewall.hostname,
        management_ip=(
            firewall.management.ip_address
            if firewall.management is not None
            else None
        ),
        serial_number=firewall.serial,
        firewall=firewall,
    )