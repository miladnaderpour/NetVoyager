"""Associate network devices with BGP prefixes and site scopes."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from ipaddress import IPv4Network

from netvoyager_core.logging import get_logger
from netvoyager_network.bgp.matching import (
    build_prefix_index,
    find_most_specific_matches_indexed,
)
from netvoyager_network.bgp.models import AsPrefix
from netvoyager_network.device.models import NetworkDevice
from netvoyager_network.scope.models import NetworkScope

from ..findings.models import Finding
from ..findings.store import FindingStore
from .models import SitePrefixAnalysisResult, SitePrefixAssociation


logger = get_logger("netvoyager.analysis.ipam.processing")


def analyze_site_prefixes(
    devices: Iterable[NetworkDevice],
    prefixes: Iterable[AsPrefix],
    scopes: Mapping[str, NetworkScope],
    *,
    finding_store: FindingStore,
    min_prefix_length: int | None = 16,
) -> SitePrefixAnalysisResult:
    """Associate device management IPs with BGP prefixes and site scopes.

    For every device with a management IP and site assignment:

    - Find all most-specific BGP prefix observations containing the address.
    - Reject matches broader than the configured minimum prefix length.
    - Associate eligible IPv4 networks and ASNs with the device's site scope.
    - Group devices by site and matched IPv4 network.
    - Preserve all matching AsPrefix observations for the longest prefix.
    - Record findings for missing data, unmatched addresses, broad matches,
      missing site scopes, and prefixes associated with multiple sites.

    This function modifies the supplied NetworkScope objects by adding direct
    prefix and ASN associations. Devices and AsPrefix objects are not modified.
    """
    device_list = list(
        devices
    )
    prefix_list = list(
        prefixes
    )

    prefix_index = build_prefix_index(
        prefix_list
    )

    association_devices: dict[
        tuple[str, IPv4Network],
        dict[object, NetworkDevice],
    ] = defaultdict(dict)

    association_prefixes: dict[
        tuple[str, IPv4Network],
        list[AsPrefix],
    ] = defaultdict(list)

    prefix_sites: dict[
        IPv4Network,
        set[str],
    ] = defaultdict(set)

    matched_device_ids: set[object] = set()

    for device in device_list:
        if device.management_ip is None:
            finding_store.add(
                Finding(
                    kind="device_missing_management_ip",
                    severity="warning",
                    message=(
                        f"Device {device.name} has no management IP "
                        "for prefix analysis"
                    ),
                    object_type="network_device",
                    object_id=device.device_id,
                    details={
                        "device_name": device.name,
                        "site": device.site,
                    },
                )
            )
            continue

        if not device.site:
            finding_store.add(
                Finding(
                    kind="device_missing_site",
                    severity="warning",
                    message=(
                        f"Device {device.name} has no site assignment "
                        "for prefix analysis"
                    ),
                    object_type="network_device",
                    object_id=device.device_id,
                    details={
                        "device_name": device.name,
                        "management_ip": device.management_ip,
                    },
                )
            )
            continue

        scope = scopes.get(
            device.site
        )

        if scope is None:
            finding_store.add(
                Finding(
                    kind="device_site_scope_not_found",
                    severity="warning",
                    message=(
                        f"Site scope {device.site!r} was not found for "
                        f"device {device.name}"
                    ),
                    object_type="network_device",
                    object_id=device.device_id,
                    details={
                        "device_name": device.name,
                        "site": device.site,
                        "management_ip": device.management_ip,
                    },
                )
            )
            continue

        match_result = find_most_specific_matches_indexed(
            device.management_ip,
            prefix_index,
            min_prefix_length=min_prefix_length,
            skip_broad_matches=True,
        )

        if match_result.is_broader_than_expected:
            finding_store.add(
                Finding(
                    kind="device_only_broad_prefix_match",
                    severity="warning",
                    message=(
                        f"Device {device.name} management IP "
                        f"{device.management_ip} matched only a BGP prefix "
                        f"broader than /{min_prefix_length}"
                    ),
                    object_type="network_device",
                    object_id=device.device_id,
                    details={
                        "device_name": device.name,
                        "site": device.site,
                        "management_ip": device.management_ip,
                        "matched_prefix_length": (
                            match_result.matched_prefix_length
                        ),
                        "min_prefix_length": min_prefix_length,
                    },
                )
            )
            continue

        if not match_result.matches:
            finding_store.add(
                Finding(
                    kind="device_no_matching_prefix",
                    severity="warning",
                    message=(
                        f"Device {device.name} management IP "
                        f"{device.management_ip} does not match "
                        "any supplied BGP prefix"
                    ),
                    object_type="network_device",
                    object_id=device.device_id,
                    details={
                        "device_name": device.name,
                        "site": device.site,
                        "management_ip": device.management_ip,
                    },
                )
            )
            continue

        matched_device_ids.add(
            device.device_id
        )

        for prefix in match_result.matches:
            key = (
                device.site,
                prefix.prefix,
            )

            association_devices[
                key
            ][
                device.device_id
            ] = device

            if all(
                existing.id != prefix.id
                for existing in association_prefixes[key]
            ):
                association_prefixes[
                    key
                ].append(prefix)

            prefix_sites[
                prefix.prefix
            ].add(
                device.site
            )

            if prefix.prefix not in scope.prefixes:
                scope.add_prefix(
                    prefix.prefix
                )

            if prefix.asn not in scope.asns:
                scope.add_asn(
                    prefix.asn
                )

    associations: list[
        SitePrefixAssociation
    ] = []

    for key, devices_by_id in association_devices.items():
        site, network = key
        prefix_records = association_prefixes[
            key
        ]

        for prefix in prefix_records:
            associations.append(
                SitePrefixAssociation(
                    site=site,
                    prefix=prefix,
                    devices=tuple(
                        devices_by_id.values()
                    ),
                )
            )

    for network, sites in prefix_sites.items():
        if len(sites) <= 1:
            continue

        finding_store.add(
            Finding(
                kind="prefix_multiple_sites",
                severity="warning",
                message=(
                    f"Prefix {network} is associated with multiple sites"
                ),
                object_type="ipv4_prefix",
                object_id=str(network),
                details={
                    "prefix": network,
                    "sites": tuple(
                        sorted(sites)
                    ),
                },
            )
        )

    logger.info(
        "Site prefix analysis complete: devices=%d, matched_devices=%d, "
        "associations=%d, site_prefixes=%d",
        len(device_list),
        len(matched_device_ids),
        len(associations),
        len(prefix_sites),
    )

    return SitePrefixAnalysisResult(
        associations=tuple(
            associations
        ),
    )