"""Process canonical network prefixes and analyze site-prefix relationships."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from uuid import UUID

from netvoyager_core.logging import get_logger
from netvoyager_network.bgp.models import AsPrefix
from netvoyager_network.device.models import NetworkDevice
from netvoyager_network.ipam.matching import (
    build_prefix_index,
    find_most_specific_match_indexed,
)
from netvoyager_network.ipam.models import NetworkPrefix
from netvoyager_network.scope.models import NetworkScope

from ..evidence.store import EvidenceStore
from ..findings.models import Finding
from ..findings.store import FindingStore
from .models import (
    SitePrefixAnalysisResult,
    SitePrefixAssociation,
)
from .store import NetworkPrefixStore


logger = get_logger(
    "netvoyager.analysis.ipam.processing"
)


def process_network_prefixes(
    as_prefixes: Iterable[AsPrefix],
    *,
    network_prefix_store: NetworkPrefixStore,
    evidence_store: EvidenceStore,
) -> tuple[NetworkPrefix, ...]:
    """Create canonical NetworkPrefix objects from BGP prefix observations.

    Create or reuse one canonical NetworkPrefix for every exact IPv4 network
    observed through AsPrefix records.

    Existing evidence linked to each AsPrefix is also linked to the
    corresponding canonical NetworkPrefix.

    Preserve the first encounter order of unique IPv4 networks. Repeated
    AsPrefix observations for the same exact network reuse the same
    NetworkPrefix object.

    The supplied AsPrefix objects and evidence records are not modified.
    """
    network_prefixes_by_id: dict[
        UUID,
        NetworkPrefix,
    ] = {}

    observation_count = 0
    created_count = 0
    reused_count = 0
    evidence_link_count = 0

    for as_prefix in as_prefixes:
        observation_count += 1

        network_prefix, created = (
            network_prefix_store.get_or_create(
                as_prefix.prefix
            )
        )

        network_prefixes_by_id.setdefault(
            network_prefix.id,
            network_prefix,
        )

        if created:
            created_count += 1
        else:
            reused_count += 1

        evidence_records = (
            evidence_store.for_object(
                "as_prefix",
                as_prefix.id,
            )
        )

        for evidence in evidence_records:
            evidence_store.link(
                evidence.id,
                "network_prefix",
                network_prefix.id,
            )

            evidence_link_count += 1

        logger.debug(
            "Network prefix processed",
            extra={
                "prefix": str(
                    as_prefix.prefix
                ),
                "asn": as_prefix.asn,
                "as_prefix_id": str(
                    as_prefix.id
                ),
                "network_prefix_id": str(
                    network_prefix.id
                ),
                "network_prefix_created": created,
                "evidence_count": len(
                    evidence_records
                ),
            },
        )

    result = tuple(
        network_prefixes_by_id.values()
    )

    logger.info(
        "Network prefix processing completed",
        extra={
            "as_prefix_observations": (
                observation_count
            ),
            "network_prefixes": len(
                result
            ),
            "created_prefixes": created_count,
            "reused_observations": reused_count,
            "evidence_links": evidence_link_count,
            "store_size": len(
                network_prefix_store
            ),
        },
    )

    return result


def analyze_site_prefixes(
    devices: Iterable[NetworkDevice],
    scopes: Mapping[str, NetworkScope],
    *,
    finding_store: FindingStore,
    network_prefix_store: NetworkPrefixStore,
    min_prefix_length: int | None = 16,
) -> SitePrefixAnalysisResult:
    """Associate device management addresses with canonical network prefixes.

    For every device with a management IP and site assignment:

    - Find the most-specific canonical NetworkPrefix containing the address.
    - Reject matches broader than the configured minimum prefix length.
    - Associate the matched NetworkPrefix UUID with the device's site scope.
    - Group devices by site and canonical NetworkPrefix.
    - Record findings for missing data, unmatched addresses, broad matches,
      missing site scopes, and prefixes associated with multiple sites.

    This function does not create NetworkPrefix objects, inspect AsPrefix
    observations, copy evidence, or infer autonomous-system relationships.

    The supplied NetworkScope objects may be modified by adding canonical
    NetworkPrefix UUID associations. NetworkDevice and NetworkPrefix objects
    are not modified.
    """
    device_list = list(
        devices
    )

    network_prefixes = (
        network_prefix_store.values()
    )

    prefix_index = build_prefix_index(
        network_prefixes
    )

    association_devices: dict[
        tuple[str, UUID],
        dict[object, NetworkDevice],
    ] = defaultdict(dict)

    association_prefixes: dict[
        tuple[str, UUID],
        NetworkPrefix,
    ] = {}

    prefix_sites: dict[
        UUID,
        set[str],
    ] = defaultdict(set)

    prefixes_by_id: dict[
        UUID,
        NetworkPrefix,
    ] = {
        prefix.id: prefix
        for prefix in network_prefixes
    }

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
                        "management_ip": (
                            device.management_ip
                        ),
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
                        "management_ip": (
                            device.management_ip
                        ),
                    },
                )
            )
            continue

        match_result = (
            find_most_specific_match_indexed(
                device.management_ip,
                prefix_index,
                min_prefix_length=(
                    min_prefix_length
                ),
                skip_broad_matches=True,
            )
        )

        if match_result.is_broader_than_expected:
            finding_store.add(
                Finding(
                    kind="device_only_broad_prefix_match",
                    severity="warning",
                    message=(
                        f"Device {device.name} management IP "
                        f"{device.management_ip} matched only a prefix "
                        f"broader than /{min_prefix_length}"
                    ),
                    object_type="network_device",
                    object_id=device.device_id,
                    details={
                        "device_name": device.name,
                        "site": device.site,
                        "management_ip": (
                            device.management_ip
                        ),
                        "matched_prefix_length": (
                            match_result.matched_prefix_length
                        ),
                        "min_prefix_length": (
                            min_prefix_length
                        ),
                    },
                )
            )
            continue

        network_prefix = match_result.match

        if network_prefix is None:
            finding_store.add(
                Finding(
                    kind="device_no_matching_prefix",
                    severity="warning",
                    message=(
                        f"Device {device.name} management IP "
                        f"{device.management_ip} does not match "
                        "any canonical network prefix"
                    ),
                    object_type="network_device",
                    object_id=device.device_id,
                    details={
                        "device_name": device.name,
                        "site": device.site,
                        "management_ip": (
                            device.management_ip
                        ),
                    },
                )
            )
            continue

        matched_device_ids.add(
            device.device_id
        )

        key = (
            device.site,
            network_prefix.id,
        )

        association_devices[
            key
        ][
            device.device_id
        ] = device

        association_prefixes[
            key
        ] = network_prefix

        prefix_sites[
            network_prefix.id
        ].add(
            device.site
        )

        if network_prefix.id not in scope.prefix_ids:
            scope.add_prefix(
                network_prefix.id
            )

    associations: list[
        SitePrefixAssociation
    ] = []

    for key, devices_by_id in (
        association_devices.items()
    ):
        site, _ = key

        network_prefix = (
            association_prefixes[
                key
            ]
        )

        associations.append(
            SitePrefixAssociation(
                site=site,
                prefix=network_prefix,
                devices=tuple(
                    devices_by_id.values()
                ),
            )
        )

    for prefix_id, sites in prefix_sites.items():
        if len(sites) <= 1:
            continue

        network_prefix = prefixes_by_id[
            prefix_id
        ]

        finding_store.add(
            Finding(
                kind="prefix_multiple_sites",
                severity="warning",
                message=(
                    f"Prefix {network_prefix.prefix} is associated "
                    "with multiple sites"
                ),
                object_type="network_prefix",
                object_id=network_prefix.id,
                details={
                    "prefix": (
                        network_prefix.prefix
                    ),
                    "sites": tuple(
                        sorted(
                            sites
                        )
                    ),
                },
            )
        )

    logger.info(
        "Site prefix analysis completed",
        extra={
            "device_count": len(
                device_list
            ),
            "matched_device_count": len(
                matched_device_ids
            ),
            "association_count": len(
                associations
            ),
            "associated_prefix_count": len(
                prefix_sites
            ),
        },
    )

    return SitePrefixAnalysisResult(
        associations=tuple(
            associations
        ),
    )