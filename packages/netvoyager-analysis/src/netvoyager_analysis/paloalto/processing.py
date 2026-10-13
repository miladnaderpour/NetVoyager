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

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace

from netvoyager_network.scope.models import NetworkScope

from ..ipam.policy import classify_site_prefix
from ..ipam.store import NetworkPrefixStore
from .subnets import iter_site_subnet_candidates



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



def resolve_firewall_scopes(
    resolutions: Iterable[PanoramaFirewallResolution],
    scopes: Mapping[str, NetworkScope],
    *,
    network_prefix_store: NetworkPrefixStore,
    finding_store: FindingStore,
    static_virtual_router: str = "vpn_intern",
    min_prefix_length: int = 13,
    connected_auto_prefix_length: int = 20,
    max_prefix_length: int = 31,
) -> tuple[PanoramaFirewallResolution, ...]:
    """Resolve firewall sites using identity and subnet observations.

    Connected eligible prefixes can support site resolution.
    Broader connected prefixes and static routes are candidates only.

    Existing devices, scopes, and canonical prefixes are not modified.
    """
    prefix_sites: dict[object, set[str]] = defaultdict(set)

    for scope_id, scope in scopes.items():
        for prefix_id in scope.prefix_ids:
            prefix_sites[prefix_id].add(scope_id)

    output: list[PanoramaFirewallResolution] = []
    candidate_count = 0
    conflict_count = 0

    for resolution in resolutions:
        firewall = resolution.firewall
        identity_site = resolution.identity_scope_id

        supported_sites: set[str] = set()
        candidates: list[dict[str, object]] = []

        for observation in iter_site_subnet_candidates(
            firewall,
            static_virtual_router=static_virtual_router,
            min_prefix_length=min_prefix_length,
            connected_auto_prefix_length=connected_auto_prefix_length,
            max_prefix_length=max_prefix_length,
        ):
            canonical = network_prefix_store.find_exact(
                observation.prefix
            )

            sites = (
                prefix_sites.get(canonical.id, set())
                if canonical is not None
                else set()
            )

            if (
                observation.source == "connected"
                and observation.decision == "eligible"
                and len(sites) == 1
            ):
                supported_sites.update(sites)
                continue

            candidates.append(
                {
                    "source": observation.source,
                    "prefix": str(observation.prefix),
                    "virtual_router": observation.virtual_router,
                    "interface": observation.interface,
                    "decision": observation.decision,
                    "known_sites": tuple(sorted(sites)),
                    "canonical_prefix_found": canonical is not None,
                }
            )

        if candidates:
            candidate_count += len(candidates)

            finding_store.add(
                Finding(
                    kind="panorama_site_prefix_candidates",
                    severity="info",
                    message=(
                        f"Panorama firewall {firewall.hostname} has "
                        "subnet observations requiring site validation"
                    ),
                    object_type="network_device",
                    object_id=(
                        resolution.device.device_id
                        if resolution.device is not None
                        else firewall.serial
                    ),
                    details={
                        "firewall_serial": firewall.serial,
                        "identity_site": identity_site,
                        "candidates": candidates,
                    },
                )
            )

        prefix_scope_ids = tuple(sorted(supported_sites))

        if identity_site is not None:
            if supported_sites and identity_site not in supported_sites:
                status = "conflict"
                conflict_count += 1
            elif len(supported_sites) > 1:
                status = "multiple_scopes"
            else:
                status = "matched"

        elif len(supported_sites) == 1:
            status = "matched"
        elif len(supported_sites) > 1:
            status = "multiple_scopes"
        else:
            status = "unresolved"

        if status == "conflict":
            finding_store.add(
                Finding(
                    kind="panorama_firewall_scope_conflict",
                    severity="warning",
                    message=(
                        f"Panorama firewall {firewall.hostname} has "
                        "conflicting identity and connected-prefix evidence"
                    ),
                    object_type="network_device",
                    object_id=(
                        resolution.device.device_id
                        if resolution.device is not None
                        else firewall.serial
                    ),
                    details={
                        "firewall_serial": firewall.serial,
                        "identity_site": identity_site,
                        "prefix_sites": prefix_scope_ids,
                    },
                )
            )

        resolved_scope_ids = tuple(
            sorted(
                supported_sites
                | ({identity_site} if identity_site else set())
            )
        )

        output.append(
            replace(
                resolution,
                status=status,
                prefix_scope_ids=prefix_scope_ids,
                resolved_scope_ids=resolved_scope_ids,
            )
        )

    logger.info(
        "Panorama firewall scope resolution completed: "
        "firewalls=%d | matched=%d | conflicts=%d | "
        "multiple_scopes=%d | unresolved=%d | candidates=%d",
        len(output),
        sum(item.status == "matched" for item in output),
        conflict_count,
        sum(item.status == "multiple_scopes" for item in output),
        sum(item.status == "unresolved" for item in output),
        candidate_count,
    )

    return tuple(output)
