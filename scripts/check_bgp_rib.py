"""Check a Palo Alto BGP RIB and optionally match inventory sites to ASNs."""

import argparse
import json
from collections import defaultdict
from ipaddress import IPv4Network
from pathlib import Path

from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import (
    InventoryReadResult,
    read_network_devices,
)
from netvoyager_network.bgp.filtering import filter_as_prefixes
from netvoyager_network.bgp.grouping import group_prefixes_by_origin_as
from netvoyager_network.bgp.models import AsSiteAssignmentResult
from netvoyager_network.bgp.site_assignment import assign_sites_to_asns
from netvoyager_paloalto.bgp.models import BgpRibResult, UnparsedLine
from netvoyager_paloalto.bgp.parser import parse_loc_rib
from netvoyager_network.bgp.models import AsPrefixes, AsSiteAssignmentResult


SCOPE = IPv4Network("10.0.0.0/8")
logger = get_logger("scripts.check_bgp_rib")


def _log_unparsed(
    label: str,
    lines: tuple[UnparsedLine, ...],
    limit: int = 10,
) -> None:
    if not lines:
        return

    logger.warning(
        "Unparsed RIB lines found",
        extra={"section": label, "unparsed_count": len(lines)},
    )

    for item in lines[:limit]:
        logger.warning(
            "Unparsed RIB line",
            extra={
                "section": label,
                "line_number": item.line_number,
                "reason": item.reason,
            },
        )

    if len(lines) > limit:
        logger.warning(
            "Additional unparsed RIB lines omitted",
            extra={
                "section": label,
                "omitted_count": len(lines) - limit,
            },
        )


def _log_inventory(inventory: InventoryReadResult) -> None:
    logger.info(
        "Inventory summary",
        extra={
            "device_count": len(inventory.devices),
            "issue_count": len(inventory.issues),
            "distinct_management_ips": len(inventory.ip_sites_mapping),
        },
    )

    for ip, sites in sorted(
        inventory.ip_sites_mapping.items(),
        key=lambda item: int(item[0]),
    ):
        site_refs = sorted(sites)

        logger.debug(
            "Inventory management IP",
            extra={
                "management_ip": str(ip),
                "site_refs": site_refs,
            },
        )

        if len(site_refs) > 1:
            logger.warning(
                "Management IP appears under multiple sites",
                extra={
                    "management_ip": str(ip),
                    "site_refs": site_refs,
                },
            )

    for issue in inventory.issues:
        # The conflict is already logged once per IP above.
        if issue.reason == "Management IP appears under multiple sites":
            continue

        logger.warning(
            "Inventory row issue",
            extra={
                "row_number": issue.row_number,
                "reason": issue.reason,
            },
        )


def _log_unresolved(result: AsSiteAssignmentResult) -> None:
    for item in result.unresolved:
        logger.warning(
            "Inventory IP could not establish an ASN-to-site link",
            extra={
                "site_ref": item.site,
                "management_ip": str(item.management_ip),
                "reason": item.reason,
            },
        )


def _log_site_conflicts(result: AsSiteAssignmentResult) -> None:
    asns_by_site: dict[str, set[int]] = defaultdict(set)

    for assignment in result.assignments:
        for site in assignment.sites:
            asns_by_site[site].add(assignment.asn)

    for site, asns in sorted(asns_by_site.items()):
        if len(asns) > 1:
            logger.warning(
                "Site matched multiple origin ASNs",
                extra={
                    "site_ref": site,
                    "origin_asns": sorted(asns),
                },
            )


def _log_final_asn_report(
    router: BgpRibResult,
    groups: tuple[AsPrefixes, ...],
    assignment_result: AsSiteAssignmentResult | None,
    inventory: InventoryReadResult | None,
) -> None:
    assignments = (
        {item.asn: item for item in assignment_result.assignments}
        if assignment_result is not None
        else {}
    )

    logger.info(
        "Final ASN report started",
        extra={
            "router_name": router.virtual_router,
            "asn_count": len(groups),
        },
    )

    for group in groups:
        assignment = assignments.get(group.asn)
        sites = assignment.sites if assignment is not None else ()

        evidence = []
        if assignment is not None:
            for item in assignment.evidence:
                known_sites = (
                    inventory.ip_sites_mapping.get(item.management_ip, ())
                    if inventory is not None
                    else ()
                )
                evidence.append({
                    "site_ref": item.site,
                    "management_ip": str(item.management_ip),
                    "matched_route": str(item.matched_prefix),
                    "cross_site_ip": len(known_sites) > 1,
                })

        logger.info(
            "Final ASN report entry",
            extra={
                "router_name": router.virtual_router,
                "origin_asn": group.asn,
                "site_refs": list(sites),
                "site_status": (
                    "not_checked"
                    if inventory is None
                    else "unassigned"
                    if not sites
                    else "single_site"
                    if len(sites) == 1
                    else "multiple_sites_review"
                ),
                "prefixes": [str(prefix) for prefix in group.prefixes],
                "site_evidence": evidence,
            },
        )

    logger.info(
        "Final ASN report completed",
        extra={
            "router_name": router.virtual_router,
            "asn_count": len(groups),
        },
    )



def _log_router(
    number: int,
    router: BgpRibResult,
    inventory: InventoryReadResult | None,
    show_prefixes: bool,
) -> None:
    parsed = len(router.routes)
    reported = router.total_routes_shown

    if reported is None:
        status = "NO FOOTER"
    elif parsed == reported:
        status = "OK"
    else:
        status = "MISMATCH"

    log_router = logger.info if status == "OK" else logger.warning
    log_router(
        "BGP router section checked",
        extra={
            "section_number": number,
            "router_name": router.virtual_router,
            "router_id": router.virtual_router_id,
            "parsed_routes": parsed,
            "reported_routes": reported,
            "status": status,
        },
    )
    _log_unparsed(router.virtual_router, router.unparsed_lines)

    groups = filter_as_prefixes(
        group_prefixes_by_origin_as(router.routes),
        SCOPE,
    )
    prefix_count = sum(len(group.prefixes) for group in groups)

    logger.info(
        "BGP prefixes within scope",
        extra={
            "router_name": router.virtual_router,
            "scope": str(SCOPE),
            "origin_asn_count": len(groups),
            "asn_prefix_entry_count": prefix_count,
        },
    )

    assignment_result = None
    sites_by_asn: dict[int, tuple[str, ...]] = {}

    if inventory is not None:
        assignment_result = assign_sites_to_asns(
            devices=inventory.devices,
            routes=router.routes,
            scope=SCOPE,
        )
        sites_by_asn = {
            assignment.asn: assignment.sites
            for assignment in assignment_result.assignments
        }

    for group in groups:
        sites = sites_by_asn.get(group.asn, ())

        logger.info(
            "Origin ASN prefix group",
            extra={
                "router_name": router.virtual_router,
                "origin_asn": group.asn,
                "prefix_count": len(group.prefixes),
                "site_refs": list(sites),
                "site_status": (
                    "not_checked"
                    if inventory is None
                    else "unassigned"
                    if not sites
                    else "single_site"
                    if len(sites) == 1
                    else "multiple_sites_review"
                ),
            },
        )

        if show_prefixes:
            for prefix in group.prefixes:
                logger.info(
                    "Origin ASN prefix",
                    extra={
                        "router_name": router.virtual_router,
                        "origin_asn": group.asn,
                        "prefix": str(prefix),
                    },
                )

    if assignment_result is None:
        return

    logger.info(
        "Inventory matching summary",
        extra={
            "router_name": router.virtual_router,
            "asns_with_site_evidence": len(assignment_result.assignments),
            "unresolved_ip_count": len(assignment_result.unresolved),
            "skipped_device_count": assignment_result.skipped_devices,
        },
    )

    for assignment in assignment_result.assignments:
        for evidence in assignment.evidence:
            logger.info(
                "ASN-to-site evidence",
                extra={
                    "router_name": router.virtual_router,
                    "origin_asn": assignment.asn,
                    "site_ref": evidence.site,
                    "management_ip": str(evidence.management_ip),
                    "matched_prefix": str(evidence.matched_prefix),
                },
            )

    _log_unresolved(assignment_result)
    _log_site_conflicts(assignment_result)
    _log_final_asn_report(router, groups, assignment_result, inventory)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check a Palo Alto BGP local RIB and match inventory sites."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to a local RIB output file",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        help="Path to an Excel network inventory",
    )
    parser.add_argument(
        "--show-prefixes",
        action="store_true",
        help="Log every prefix grouped under its origin ASN",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log individual inventory IP-to-site mappings",
    )
    args = parser.parse_args()

    level = "DEBUG" if args.debug else "INFO"
    setup_logging(
        LoggingSettings(
            targets_json=json.dumps([
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
                    "file_path": "logs/check_bgp_rib.log",
                },
            ])
        )
    )

    inventory = (
        read_network_devices(args.inventory)
        if args.inventory is not None
        else None
    )
    if inventory is not None:
        _log_inventory(inventory)

    dump = parse_loc_rib(args.file.read_text(encoding="utf-8"))

    logger.info(
        "BGP RIB sections found",
        extra={"section_count": len(dump.routers)},
    )

    for number, router in enumerate(dump.routers, start=1):
        _log_router(number, router, inventory, args.show_prefixes)

    logger.info(
        "BGP RIB check completed",
        extra={
            "section_count": len(dump.routers),
            "total_parsed_routes": sum(
                len(router.routes) for router in dump.routers
            ),
        },
    )
    _log_unparsed("Outside router sections", dump.unparsed_lines)
    


if __name__ == "__main__":
    main()