"""Test site-prefix analysis using inventory devices and vpn_intern BGP routes."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.bgp.processing import process_bgp_routes
from netvoyager_analysis.devices.processing import process_device_observations
from netvoyager_analysis.devices.scopes import build_site_scopes
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_analysis.findings.adapters import add_inventory_issues
from netvoyager_analysis.findings.store import FindingStore
from netvoyager_analysis.ipam.processing import analyze_site_prefixes
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import read_network_devices
from netvoyager_paloalto.bgp import parse_loc_rib


logger = get_logger(
    "netvoyager.scripts.test_site_prefix_analysis"
)

TARGET_VIRTUAL_ROUTER = "vpn_intern"
DEFAULT_MIN_PREFIX_LENGTH = 16


def main() -> None:
    """Test site-prefix analysis using inventory and vpn_intern BGP routes."""
    parser = argparse.ArgumentParser(
        description=(
            "Test inventory site-prefix analysis using "
            "the vpn_intern Palo Alto BGP local RIB."
        ),
    )

    parser.add_argument(
        "inventory",
        type=Path,
        help="Path to the network device inventory Excel file.",
    )

    parser.add_argument(
        "rib",
        type=Path,
        help="Path to the Palo Alto BGP local RIB text file.",
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
        help="RIB text encoding (default: utf-8-sig).",
    )

    parser.add_argument(
        "--min-prefix-length",
        type=int,
        default=DEFAULT_MIN_PREFIX_LENGTH,
        help=(
            "Minimum BGP prefix length eligible for site association "
            f"(default: {DEFAULT_MIN_PREFIX_LENGTH}). "
            "Broader matches are rejected."
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
                        "file_path": str(log_path),
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

    logger.info(
        "Inventory source: %s",
        inventory_source,
    )

    logger.info(
        "BGP RIB source: %s",
        rib_source,
    )

    logger.info(
        "Target virtual router: %s",
        TARGET_VIRTUAL_ROUTER,
    )

    logger.info(
        "Minimum site prefix length: /%d",
        args.min_prefix_length,
    )

    if args.sheet is not None:
        logger.info(
            "Inventory worksheet: %s",
            args.sheet,
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
        len(inventory_result.observations),
        len(inventory_result.issues),
    )

    #
    # Shared evidence and finding stores.
    #
    evidence_store = EvidenceStore()
    finding_store = FindingStore()

    #
    # Convert inventory import issues into findings.
    #
    add_inventory_issues(
        inventory_result.issues,
        finding_store=finding_store,
    )

    logger.info(
        "Inventory findings imported: %d",
        len(finding_store.findings),
    )

    #
    # Create NetworkDevice objects.
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
        len(devices),
    )

    #
    # Build baseline site scopes from inventory.
    #
    scopes = build_site_scopes(
        devices
    )

    logger.info(
        "Baseline site scopes created: %d",
        len(scopes),
    )

    #
    # Read Palo Alto BGP local RIB.
    #
    try:
        raw_rib = args.rib.read_text(
            encoding=args.encoding,
        )
    except (
        OSError,
        UnicodeError,
        LookupError,
    ) as exc:
        parser.error(
            f"Cannot read BGP RIB: {exc}"
        )

    #
    # Parse virtual-router sections.
    #
    try:
        rib_result = parse_loc_rib(
            raw_rib
        )
    except ValueError as exc:
        parser.error(
            f"Cannot parse BGP RIB: {exc}"
        )

    logger.info(
        "BGP virtual-router sections parsed: %d",
        len(rib_result.routers),
    )

    available_routers = [
        router.virtual_router
        for router in rib_result.routers
    ]

    logger.info(
        "Available virtual routers: %s",
        available_routers,
    )

    #
    # Use vpn_intern only.
    #
    router = next(
        (
            router
            for router in rib_result.routers
            if router.virtual_router
            == TARGET_VIRTUAL_ROUTER
        ),
        None,
    )

    if router is None:
        parser.error(
            f"Virtual router {TARGET_VIRTUAL_ROUTER!r} "
            f"was not found. "
            f"Available routers: {available_routers}"
        )

    logger.info(
        "Using virtual router: %s | routes=%d",
        router.virtual_router,
        len(router.routes),
    )

    #
    # Convert vpn_intern routes into AsPrefix objects.
    #
    prefixes = process_bgp_routes(
        router.routes,
        source=rib_source,
        evidence_store=evidence_store,
        context={
            "virtual_router": (
                router.virtual_router
            ),
            "virtual_router_id": (
                router.virtual_router_id
            ),
        },
    )

    unknown_origins = (
        len(router.routes)
        - len(prefixes)
    )

    logger.info(
        "BGP totals for %s: routes=%d, prefixes=%d, "
        "unknown_origins=%d",
        router.virtual_router,
        len(router.routes),
        len(prefixes),
        unknown_origins,
    )

    #
    # Perform initial BGP-based site-prefix analysis.
    #
    analysis_result = analyze_site_prefixes(
        devices,
        prefixes,
        scopes,
        finding_store=finding_store,
        min_prefix_length=args.min_prefix_length,
    )

    #
    # Scope totals after analysis.
    #
    total_scope_prefixes = sum(
        len(scope.prefixes)
        for scope in scopes.values()
    )

    total_scope_asns = sum(
        len(scope.asns)
        for scope in scopes.values()
    )

    logger.info(
        "IPAM analysis summary: associations=%d, "
        "matched_devices=%d, "
        "scope_prefix_assignments=%d, "
        "scope_asn_assignments=%d",
        len(analysis_result.associations),
        len(analysis_result.matched_devices),
        total_scope_prefixes,
        total_scope_asns,
    )

    #
    # Finding summary.
    #
    finding_counts = Counter(
        finding.kind
        for finding in finding_store.findings
    )

    logger.info(
        "Finding totals: total=%d, kinds=%d",
        len(finding_store.findings),
        len(finding_counts),
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
            "asn=%s | "
            "devices=%d | "
            "prefix_id=%s",
            association.site,
            association.prefix.prefix,
            association.prefix.asn,
            len(association.devices),
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
    # Detailed site summaries when debug logging is enabled.
    #
    for scope in scopes.values():
        if (
            not scope.prefixes
            and not scope.asns
        ):
            continue

        logger.debug(
            "SITE: %s | devices=%d | prefixes=%d | asns=%d",
            scope.scope_id,
            len(scope.devices),
            len(scope.prefixes),
            len(scope.asns),
        )

        for prefix in sorted(
            scope.prefixes
        ):
            logger.debug(
                "  PREFIX: site=%s | prefix=%s",
                scope.scope_id,
                prefix,
            )

        for asn in sorted(
            scope.asns
        ):
            logger.debug(
                "  ASN: site=%s | asn=%d",
                scope.scope_id,
                asn,
            )

    #
    # Final evidence totals.
    #
    logger.info(
        "Evidence totals: records=%d, relations=%d",
        len(evidence_store.records),
        len(evidence_store.relations),
    )

    logger.info(
        "Log file: %s",
        log_path.resolve(),
    )


if __name__ == "__main__":
    main()