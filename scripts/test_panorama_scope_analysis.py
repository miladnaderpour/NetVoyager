"""Integrate inventory, BGP site prefixes, and Panorama firewall site discovery."""

import argparse
import json
from collections import Counter
from ipaddress import IPv4Network
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.bgp.processing import process_bgp_routes
from netvoyager_analysis.devices.legacy_processing import process_device_observations
from netvoyager_analysis.devices.scopes import build_site_scopes
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_analysis.findings.adapters import add_inventory_issues
from netvoyager_analysis.findings.store import FindingStore
from netvoyager_analysis.ipam.asn import associate_scope_autonomous_systems
from netvoyager_analysis.paloalto.processing import (
    resolve_firewall_identities,
    resolve_firewall_scopes,
)
from netvoyager_analysis.ipam.processing import (
    analyze_site_prefixes,
    process_network_prefixes,
)
from netvoyager_analysis.ipam.store import NetworkPrefixStore
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import read_network_devices
from netvoyager_paloalto.bgp import (
    parse_bgp_summary,
    parse_loc_rib,
)
from netvoyager_paloalto.inventory.parser import parse_panorama_inventory


logger = get_logger(
    "netvoyager.scripts.test_panorama_scope_analysis"
)


TARGET_VIRTUAL_ROUTER = "vpn_intern"
DEFAULT_MIN_PREFIX_LENGTH = 16
DEFAULT_EXCLUDED_NETWORKS = (IPv4Network("10.127.24.0/23"),)


def _select_router(
    routers,
    virtual_router: str,
):
    """Return the requested parsed virtual-router section."""
    router = next(
        (
            router
            for router in routers
            if router.virtual_router == virtual_router
        ),
        None,
    )

    if router is None:
        available = [
            router.virtual_router
            for router in routers
        ]

        raise ValueError(
            f"Virtual router {virtual_router!r} was not found. "
            f"Available routers: {available}"
        )

    return router


def main() -> None:
    """Run the inventory/BGP baseline, then correlate Panorama firewalls."""
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "inventory",
        type=Path,
        help="Path to the network device inventory Excel file.",
    )

    parser.add_argument(
        "rib",
        type=Path,
        help=(
            "Path to Palo Alto "
            "`show routing protocol bgp loc-rib` output."
        ),
    )

    parser.add_argument(
        "--summary",
        type=Path,
        required=True,
        help=(
            "Path to Palo Alto "
            "`show routing protocol bgp summary` output."
        ),
    )

    parser.add_argument(
        "panorama",
        type=Path,
        help="Path to Panorama inventory JSON v2.0/v2.1.",
    )

    parser.add_argument(
        "--sheet",
        help=(
            "Inventory worksheet name. "
            "Uses the active sheet when omitted."
        ),
    )

    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Input text encoding (default: utf-8-sig).",
    )

    parser.add_argument(
        "--min-prefix-length",
        type=int,
        default=DEFAULT_MIN_PREFIX_LENGTH,
        help=(
            "Minimum prefix length eligible for site association "
            f"(default: {DEFAULT_MIN_PREFIX_LENGTH})."
        ),
    )

    parser.add_argument(
        "--exclude-network",
        type=IPv4Network,
        action="append",
        default=None,
        metavar="CIDR",
        help=(
            "Exclude a network range from BGP-derived site matching. "
            "Can be repeated. Default: 10.127.24.0/23."
        ),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args()

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    level = (
        "DEBUG"
        if args.debug
        else "INFO"
    )

    log_path = Path(
        f"logs/panorama_scope_analysis_{timestamp}.log"
    )

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    setup_logging(
        LoggingSettings(
            targets_json=json.dumps(
                [
                    {
                        "name": "console",
                        "output": "stdout",
                        "level": level,
                        "format": "text",
                    },
                    {
                        "name": "file",
                        "output": "file",
                        "level": level,
                        "format": "text",
                        "file_path": str(
                            log_path
                        ),
                    },
                ]
            )
        )
    )

    inventory_source = str(
        args.inventory.resolve()
    )

    rib_source = str(
        args.rib.resolve()
    )

    summary_source = str(
        args.summary.resolve()
    )
    panorama_source = str(args.panorama.resolve())

    logger.info(
        "Inventory source: %s",
        inventory_source,
    )

    logger.info(
        "BGP RIB source: %s",
        rib_source,
    )

    logger.info(
        "BGP summary source: %s",
        summary_source,
    )

    logger.info("Panorama source: %s", panorama_source)

    logger.info(
        "Target virtual router: %s",
        TARGET_VIRTUAL_ROUTER,
    )

    logger.info(
        "Minimum site prefix length: /%d",
        args.min_prefix_length,
    )

    excluded_networks = tuple(
        args.exclude_network
        if args.exclude_network is not None
        else DEFAULT_EXCLUDED_NETWORKS
    )
    logger.info("Excluded site networks: %s", tuple(map(str, excluded_networks)))

    #
    # Read inventory.
    #
    try:
        inventory_result = read_network_devices(
            args.inventory,
            sheet_name=args.sheet,
        )
    except (
        OSError,
        ValueError,
    ) as exc:
        parser.error(
            f"Cannot read inventory: {exc}"
        )

    logger.info(
        "Inventory parsed: observations=%d, issues=%d",
        len(
            inventory_result.observations
        ),
        len(
            inventory_result.issues
        ),
    )

    #
    # Shared stores.
    #
    evidence_store = EvidenceStore()
    finding_store = FindingStore()
    network_prefix_store = NetworkPrefixStore()

    #
    # Inventory findings.
    #
    add_inventory_issues(
        inventory_result.issues,
        finding_store=finding_store,
    )

    #
    # Build NetworkDevice objects.
    #
    inventory_context: dict[
        str,
        object,
    ] = {}

    if args.sheet is not None:
        inventory_context[
            "sheet"
        ] = args.sheet

    devices = process_device_observations(
        inventory_result.observations,
        source=inventory_source,
        evidence_store=evidence_store,
        context=inventory_context,
    )

    logger.info(
        "Inventory devices created: %d",
        len(
            devices
        ),
    )

    #
    # Build baseline site scopes.
    #
    scopes = build_site_scopes(
        devices
    )

    logger.info(
        "Baseline site scopes created: %d",
        len(
            scopes
        ),
    )

    #
    # Read BGP local RIB.
    #
    try:
        raw_rib = args.rib.read_text(
            encoding=args.encoding
        )
    except (
        OSError,
        UnicodeError,
        LookupError,
    ) as exc:
        parser.error(
            f"Cannot read BGP RIB: {exc}"
        )

    try:
        rib_result = parse_loc_rib(
            raw_rib
        )
    except ValueError as exc:
        parser.error(
            f"Cannot parse BGP RIB: {exc}"
        )

    try:
        router = _select_router(
            rib_result.routers,
            TARGET_VIRTUAL_ROUTER,
        )
    except ValueError as exc:
        parser.error(
            str(exc)
        )

    logger.info(
        "Using virtual router: %s | routes=%d",
        router.virtual_router,
        len(
            router.routes
        ),
    )

    #
    # Read BGP summary and obtain local ASN.
    #
    try:
        raw_summary = args.summary.read_text(
            encoding=args.encoding
        )
    except (
        OSError,
        UnicodeError,
        LookupError,
    ) as exc:
        parser.error(
            f"Cannot read BGP summary: {exc}"
        )

    try:
        bgp_summary = parse_bgp_summary(
            raw_summary
        )
    except ValueError as exc:
        parser.error(
            f"Cannot parse BGP summary: {exc}"
        )

    if (
        bgp_summary.virtual_router
        != router.virtual_router
    ):
        parser.error(
            "BGP summary virtual router does not match "
            "the selected RIB virtual router: "
            f"{bgp_summary.virtual_router!r} != "
            f"{router.virtual_router!r}"
        )

    logger.info(
        "BGP summary: virtual_router=%s | local_asn=%s",
        bgp_summary.virtual_router,
        bgp_summary.local_asn,
    )

    #
    # Process BGP observations.
    #
    bgp_result = process_bgp_routes(
        router.routes,
        source=rib_source,
        evidence_store=evidence_store,
        local_asn=bgp_summary.local_asn,
        context={
            "virtual_router": (
                router.virtual_router
            ),
            "virtual_router_id": (
                router.virtual_router_id
            ),
        },
    )

    logger.info(
        "BGP processing: "
        "routes=%d | "
        "as_prefixes=%d | "
        "autonomous_systems=%d | "
        "local_routes=%d | "
        "unknown_origins=%d",
        len(
            router.routes
        ),
        len(
            bgp_result.as_prefixes
        ),
        len(
            bgp_result.autonomous_systems
        ),
        bgp_result.local_route_count,
        bgp_result.unknown_origin_count,
    )

    #
    # Canonicalize BGP prefixes into NetworkPrefix.
    #
    network_prefixes = process_network_prefixes(
        bgp_result.as_prefixes,
        network_prefix_store=network_prefix_store,
        evidence_store=evidence_store,
    )

    logger.info(
        "Canonical IPAM prefixes: "
        "as_prefixes=%d | "
        "network_prefixes=%d | "
        "store_size=%d",
        len(
            bgp_result.as_prefixes
        ),
        len(
            network_prefixes
        ),
        len(
            network_prefix_store
        ),
    )

    #
    # Associate device management IPs with canonical NetworkPrefix objects.
    #
    # Exclude /32 host routes from BGP-derived site assignment.
    # The records remain in the canonical prefix store and evidence.
    host_prefixes = tuple(
        prefix.prefix
        for prefix in network_prefix_store.values()
        if prefix.prefix.prefixlen == 32
    )
    logger.info("Site matching: excluding %d /32 host prefixes", len(host_prefixes))

    analysis_result = analyze_site_prefixes(
        devices,
        scopes,
        finding_store=finding_store,
        network_prefix_store=network_prefix_store,
        min_prefix_length=args.min_prefix_length,
        excluded_networks=(*excluded_networks, *host_prefixes),
    )

    #
    # Scope totals.
    #
    total_scope_prefixes = sum(
        len(
            scope.prefix_ids
        )
        for scope in scopes.values()
    )

    logger.info(
        "Site-prefix analysis summary: "
        "scopes=%d | "
        "associations=%d | "
        "matched_devices=%d | "
        "canonical_prefixes=%d | "
        "scope_prefix_assignments=%d",
        len(
            scopes
        ),
        len(
            analysis_result.associations
        ),
        len(
            analysis_result.matched_devices
        ),
        len(
            network_prefix_store
        ),
        total_scope_prefixes,
    )

    #
    # Correlate scope ASNs using BGP origin observations.
    #
    new_asn_assignments = associate_scope_autonomous_systems(
        scopes,
        bgp_result.as_prefixes,
        bgp_result.autonomous_systems,
        network_prefix_store=network_prefix_store,
        finding_store=finding_store,
    )
    logger.info(
        "Site ASN correlation: new_assignments=%d | total_assignments=%d",
        new_asn_assignments,
        sum(len(scope.asns) for scope in scopes.values()),
    )

    #
    # Parse Panorama inventory and resolve identities.
    #
    try:
        raw_panorama = args.panorama.read_text(encoding=args.encoding)
    except (OSError, UnicodeError, LookupError) as exc:
        parser.error(f"Cannot read Panorama inventory: {exc}")

    try:
        panorama_result = parse_panorama_inventory(raw_panorama)
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(f"Cannot parse Panorama inventory: {exc}")

    logger.info(
        "Panorama parsed: firewalls=%d | issues=%d | failures=%d",
        len(panorama_result.firewalls),
        len(panorama_result.issues),
        len(panorama_result.collection_failures),
    )

    identity_resolutions = resolve_firewall_identities(
        panorama_result.firewalls,
        devices,
        finding_store=finding_store,
    )
    logger.info(
        "Panorama identity resolution: statuses=%s | methods=%s",
        dict(Counter(r.status for r in identity_resolutions)),
        dict(Counter(r.matched_by for r in identity_resolutions if r.matched_by)),
    )

    resolutions = resolve_firewall_scopes(
        identity_resolutions,
        scopes,
        network_prefix_store=network_prefix_store,
        finding_store=finding_store,
    )
    logger.info(
        "Panorama scope resolution: firewalls=%d | statuses=%s | "
        "identity_scopes=%d | prefix_scopes=%d | multi_scope=%d",
        len(resolutions),
        dict(Counter(r.status for r in resolutions)),
        sum(bool(r.identity_scope_id) for r in resolutions),
        sum(bool(r.prefix_scope_ids) for r in resolutions),
        sum(len(r.resolved_scope_ids) > 1 for r in resolutions),
    )

    for resolution in resolutions:
        logger.info(
            "FIREWALL: hostname=%s | serial=%s | status=%s | "
            "matched_by=%s | device=%s | identity_scope=%s | "
            "prefix_scopes=%s | resolved_scopes=%s",
            resolution.firewall.hostname,
            resolution.firewall.serial,
            resolution.status,
            resolution.matched_by,
            resolution.device.name if resolution.device else None,
            resolution.identity_scope_id,
            resolution.prefix_scope_ids,
            resolution.resolved_scope_ids,
        )

    #
    # Finding summary.
    #
    finding_counts = Counter(
        finding.kind
        for finding in finding_store.findings
    )

    logger.info(
        "Finding totals: total=%d | kinds=%d",
        len(
            finding_store.findings
        ),
        len(
            finding_counts
        ),
    )

    for kind, count in sorted(
        finding_counts.items()
    ):
        logger.info(
            "Finding kind: %s=%d",
            kind,
            count,
        )

    #
    # Site-prefix associations.
    #
    for association in analysis_result.associations:
        logger.info(
            "ASSOCIATION: "
            "site=%s | "
            "prefix=%s | "
            "devices=%d | "
            "prefix_id=%s",
            association.site,
            association.prefix.prefix,
            len(
                association.devices
            ),
            association.prefix.id,
        )

    #
    # Findings.
    #
    for finding in finding_store.findings:
        logger.warning(
            "FINDING: "
            "kind=%s | "
            "severity=%s | "
            "object_type=%s | "
            "object_id=%s | "
            "message=%s | "
            "details=%s",
            finding.kind,
            finding.severity,
            finding.object_type,
            finding.object_id,
            finding.message,
            finding.details,
        )

    #
    # Detailed site summaries.
    #
    for scope in scopes.values():
        if not scope.prefix_ids:
            continue

        logger.debug(
            "SITE: %s | devices=%d | prefixes=%d",
            scope.scope_id,
            len(
                scope.devices
            ),
            len(
                scope.prefix_ids
            ),
        )

        site_prefixes = [
            network_prefix_store.get(
                prefix_id
            )
            for prefix_id in scope.prefix_ids
        ]

        site_prefixes = [
            network_prefix
            for network_prefix in site_prefixes
            if network_prefix is not None
        ]

        for network_prefix in sorted(
            site_prefixes,
            key=lambda item: (
                int(
                    item.prefix.network_address
                ),
                item.prefix.prefixlen,
            ),
        ):
            logger.debug(
                "  PREFIX: site=%s | prefix=%s | prefix_id=%s",
                scope.scope_id,
                network_prefix.prefix,
                network_prefix.id,
            )

    #
    # Final totals.
    #
    logger.info(
        "NetworkPrefix store totals: prefixes=%d",
        len(
            network_prefix_store
        ),
    )

    logger.info(
        "Evidence totals: records=%d | relations=%d",
        len(
            evidence_store.records
        ),
        len(
            evidence_store.relations
        ),
    )

    logger.info(
        "Log file: %s",
        log_path.resolve(),
    )


if __name__ == "__main__":
    main()