"""Models for Palo Alto Panorama analysis results."""

from dataclasses import dataclass
from typing import Literal

from netvoyager_network.device.models import NetworkDevice
from netvoyager_paloalto.inventory.models import FirewallInventory

from ..devices.matching import MatchMethod


FirewallResolutionStatus = Literal[
    "matched",
    "unresolved",
    "multiple_scopes",
    "conflict",
]


@dataclass(frozen=True, slots=True)
class PanoramaFirewallResolution:
    """Resolved relationship between a Panorama firewall and site scopes.

    A firewall may be resolved through device identity, connected-prefix
    evidence, or both.

    Multiple scope IDs are retained when available evidence indicates that
    the firewall may be associated with more than one site. Conflicting
    evidence is preserved rather than collapsed into one scope.
    """

    firewall: FirewallInventory
    status: FirewallResolutionStatus

    device: NetworkDevice | None
    matched_by: MatchMethod | None

    identity_scope_id: str | None
    prefix_scope_ids: tuple[str, ...]

    resolved_scope_ids: tuple[str, ...]