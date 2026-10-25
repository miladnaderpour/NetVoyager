"""Test canonical site-prefix analysis using inventory and BGP data."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from ipaddress import IPv4Network

from netvoyager_analysis.bgp.processing import process_bgp_routes
from netvoyager_analysis.devices.legacy_processing import process_device_observations
from netvoyager_analysis.devices.scopes import build_site_scopes
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_analysis.findings.adapters import add_inventory_issues
from netvoyager_analysis.findings.store import FindingStore
from netvoyager_analysis.ipam.processing import (
    analyze_site_prefixes,
    process_network_prefixes,
)
from netvoyager_analysis.ipam.asn import (
    associate_scope_autonomous_systems,
)
from netvoyager_analysis.ipam.store import NetworkPrefixStore
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import read_network_devices
from netvoyager_paloalto.bgp import (
    parse_bgp_summary,
    parse_loc_rib,
)


logger = get_logger(
    "netvoyager.scripts.test_site_prefix_analysis"
)


TARGET_VIRTUAL_ROUTER = "vpn_intern"
DEFAULT_MIN_PREFIX_LENGTH = 16
EXCLUDED_SITE_NETWORKS = (
    IPv4Network("10.127.24.0/24"),
)


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
    """Test canonical site-prefix analysis end to end."""
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
        f"logs/site_prefix_analysis_{timestamp}.log"
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

    logger.info(
        "Target virtual router: %s",
        TARGET_VIRTUAL_ROUTER,
    )

    logger.info(
        "Minimum site prefix length: /%d",
        args.min_prefix_length,
    )

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
    analysis_result = analyze_site_prefixes(
        devices,
        scopes,
        finding_store=finding_store,
        network_prefix_store=network_prefix_store,
        min_prefix_length=args.min_prefix_length,
        excluded_networks=EXCLUDED_SITE_NETWORKS,
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
    # Correlate site scopes with BGP origin ASNs.
    #
    new_asn_assignments = associate_scope_autonomous_systems(
        scopes,
        bgp_result.as_prefixes,
        bgp_result.autonomous_systems,
        network_prefix_store=network_prefix_store,
        finding_store=finding_store,
    )

    total_scope_asns = sum(
        len(scope.asns)
        for scope in scopes.values()
        if scope.kind == "site"
    )

    unique_site_asns = {
        asn
        for scope in scopes.values()
        if scope.kind == "site"
        for asn in scope.asns
    }

    logger.info(
        "Site-ASN correlation summary: "
        "scopes=%d | "
        "new_assignments=%d | "
        "scope_asn_assignments=%d | "
        "unique_asns=%d",
        sum(
            scope.kind == "site"
            for scope in scopes.values()
        ),
        new_asn_assignments,
        total_scope_asns,
        len(unique_site_asns),
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
    # ASN correlation findings.
    #
    logger.info(
        "ASN correlation findings: "
        "prefix_multiple_asns=%d | "
        "asn_multiple_sites=%d | "
        "site_multiple_asns=%d | "
        "prefix_multiple_sites=%d",
        finding_counts["prefix_multiple_asns"],
        finding_counts["asn_multiple_sites"],
        finding_counts["site_multiple_asns"],
        finding_counts["prefix_multiple_sites"],
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