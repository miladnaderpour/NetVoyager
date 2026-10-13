
"""Select Panorama subnet observations suitable for site analysis."""

from collections.abc import Iterator
from dataclasses import dataclass
from ipaddress import IPv4Network
from typing import Literal

from netvoyager_paloalto.inventory.models import (
    FirewallInventory,
    InterfaceAddress,
    StaticRoute,
)

from ..ipam.policy import classify_site_prefix


@dataclass(frozen=True, slots=True)
class SiteSubnetCandidate:
    """A configured subnet observation with its source preserved."""

    source: Literal["connected", "static"]
    prefix: IPv4Network
    virtual_router: str
    interface: str
    record: InterfaceAddress | StaticRoute
    decision: Literal["candidate", "eligible"]


def is_tunnel_interface(interface: str | None) -> bool:
    """Recognize Palo Alto tunnel interfaces."""
    if not interface:
        return False

    name = interface.strip().lower()
    return name == "tunnel" or name.startswith("tunnel.")


def iter_site_subnet_candidates(
    firewall: FirewallInventory,
    *,
    static_virtual_router: str = "vpn_intern",
    min_prefix_length: int = 13,
    max_prefix_length: int = 31,
    connected_auto_prefix_length: int = 20,
) -> Iterator[SiteSubnetCandidate]:
    """Select connected and static networks for site correlation.

    Connected:
      - Any virtual router
      - Non-tunnel interfaces
      - Prefixes /13 through /31

    Static:
      - Selected virtual router only
      - Must have a non-tunnel outgoing interface
      - Prefixes /13 through /31

    Static observations remain candidates, not confirmed site ownership.
    """

    for address in firewall.interface_addresses:
        prefix = address.network

        if prefix is None or is_tunnel_interface(address.interface):
            continue

        decision = classify_site_prefix(
            prefix,
            source="connected",
            min_prefix_length=min_prefix_length,
            max_prefix_length=max_prefix_length,
            connected_auto_prefix_length=connected_auto_prefix_length,
        )

        if decision == "ignored":
            continue

        yield SiteSubnetCandidate(
            source="connected",
            prefix=prefix,
            virtual_router=address.virtual_router,
            interface=address.interface,
            record=address,
            decision=decision,
        )

    for route in firewall.static_routes:
        prefix = route.destination

        if (
            prefix is None
            or route.virtual_router != static_virtual_router
            or not route.interface
            or is_tunnel_interface(route.interface)
        ):
            continue

        decision = classify_site_prefix(
            prefix,
            source="static",
            min_prefix_length=min_prefix_length,
            max_prefix_length=max_prefix_length,
            connected_auto_prefix_length=connected_auto_prefix_length,
        )

        if decision == "ignored":
            continue

        yield SiteSubnetCandidate(
            source="static",
            prefix=prefix,
            virtual_router=route.virtual_router,
            interface=route.interface,
            record=route,
            decision=decision,
        )
