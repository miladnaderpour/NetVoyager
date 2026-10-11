"""Analyze Palo Alto Panorama firewall observations."""

from collections.abc import Iterable
from typing import cast

from netvoyager_core.logging import get_logger
from netvoyager_network.device.models import NetworkDevice
from netvoyager_paloalto.inventory.models import FirewallInventory

from ..devices.matching import match_devices
from ..findings.models import Finding
from ..findings.store import FindingStore
from .adapters import (
    PanoramaDeviceIdentity,
    adapt_panorama_firewall,
)
from .models import PanoramaFirewallResolution


logger = get_logger("netvoyager.analysis.paloalto.processing")


def resolve_firewall_identities(
    firewalls: Iterable[FirewallInventory],
    devices: Iterable[NetworkDevice],
    *,
    finding_store: FindingStore,
) -> tuple[PanoramaFirewallResolution, ...]:
    """Resolve Panorama firewalls against existing network devices.

    Each Panorama firewall is adapted into a generic device identity
    observation and matched using the shared device reconciliation logic.

    Successfully matched devices inherit their existing inventory site as the
    identity scope. Unresolved firewalls remain available for later subnet-
    based resolution.

    When a Panorama serial matches an inventory serial only after removing one
    leading zero, the match is accepted and recorded as a Finding.

    This function does not inspect connected prefixes, modify network devices,
    modify scopes, or create IPAM objects.
    """
    firewall_list = list(
        firewalls
    )

    observations = [
        adapt_panorama_firewall(
            firewall
        )
        for firewall in firewall_list
    ]

    matching_result = match_devices(
        observations,
        devices,
    )

    resolutions: list[
        PanoramaFirewallResolution
    ] = []

    for match in matching_result.matches:
        observation = cast(
            PanoramaDeviceIdentity,
            match.observation,
        )

        firewall = observation.firewall

        identity_scope_id = (
            match.device.site
            if match.device.site
            else None
        )

        resolved_scope_ids = (
            (identity_scope_id,)
            if identity_scope_id is not None
            else ()
        )

        if match.matched_by == "serial_without_leading_zero":
            finding_store.add(
                Finding(
                    kind="panorama_serial_leading_zero_mismatch",
                    severity="warning",
                    message=(
                        f"Panorama firewall {firewall.hostname} matched "
                        "inventory after removing one leading zero "
                        "from the Panorama serial number"
                    ),
                    object_type="network_device",
                    object_id=match.device.device_id,
                    details={
                        "firewall_hostname": firewall.hostname,
                        "panorama_serial": firewall.serial,
                        "inventory_serial": (
                            match.device.serial_number
                        ),
                        "device_name": match.device.name,
                        "device_id": match.device.device_id,
                        "site": match.device.site,
                    },
                )
            )

        resolutions.append(
            PanoramaFirewallResolution(
                firewall=firewall,
                status=(
                    "matched"
                    if identity_scope_id is not None
                    else "unresolved"
                ),
                device=match.device,
                matched_by=match.matched_by,
                identity_scope_id=identity_scope_id,
                prefix_scope_ids=(),
                resolved_scope_ids=resolved_scope_ids,
            )
        )

    for unresolved in matching_result.unresolved:
        observation = cast(
            PanoramaDeviceIdentity,
            unresolved.observation,
        )

        firewall = observation.firewall

        resolutions.append(
            PanoramaFirewallResolution(
                firewall=firewall,
                status="unresolved",
                device=None,
                matched_by=None,
                identity_scope_id=None,
                prefix_scope_ids=(),
                resolved_scope_ids=(),
            )
        )

    logger.info(
        "Panorama firewall identity resolution complete: "
        "firewalls=%d, matched=%d, unresolved=%d",
        len(firewall_list),
        len(matching_result.matches),
        len(matching_result.unresolved),
    )

    return tuple(
        resolutions
    )