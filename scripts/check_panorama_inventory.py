"""Check a Panorama inventory JSON export and its parsed records."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_paloalto.inventory.models import (
    FirewallInventory,
    PanoramaInventoryResult,
)
from netvoyager_paloalto.inventory.parser import parse_panorama_inventory


logger = get_logger("scripts.check_panorama_inventory")


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_counts(data: dict[str, Any]) -> Counter[str]:
    """Count source records independently of the parser."""
    counts: Counter[str] = Counter()

    for value in _array(data.get("firewalls")):
        counts["firewalls"] += 1
        firewall = _object(value)

        for value in _array(firewall.get("subnets")):
            counts["subnet_records"] += 1
            record = _object(value)

            if record.get("source") == "static":
                counts["static_routes"] += 1
            elif record.get("source") == "connected":
                counts["interface_addresses"] += 1

        for value in _array(firewall.get("virtual_routers")):
            counts["virtual_routers"] += 1
            router = _object(value)
            bgp = _object(router.get("bgp"))

            if bgp.get("enabled") is True:
                counts["bgp_enabled"] += 1

            groups = _array(bgp.get("peer_groups"))
            counts["peer_groups"] += len(groups)

            for group in groups:
                counts["peers"] += len(
                    _array(_object(group).get("peers"))
                )

            for field in (
                "import_rules",
                "export_rules",
                "redistribution_rules",
            ):
                counts[field] += len(_array(bgp.get(field)))

            counts["redistribution_profiles"] += len(
                _array(router.get("redistribution_profiles"))
            )

    counts["collection_failures"] = len(
        _array(data.get("failures"))
    )

    return counts


def _parsed_counts(
    result: PanoramaInventoryResult,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    counts["firewalls"] = len(result.firewalls)
    counts["collection_failures"] = len(result.collection_failures)

    for firewall in result.firewalls:
        counts["static_routes"] += len(firewall.static_routes)
        counts["interface_addresses"] += len(
            firewall.interface_addresses
        )
        counts["subnet_records"] += (
            len(firewall.static_routes)
            + len(firewall.interface_addresses)
        )

        for router in firewall.virtual_routers or ():
            counts["virtual_routers"] += 1
            counts["redistribution_profiles"] += len(
                router.redistribution_profiles
            )

            bgp = router.bgp
            if bgp is None:
                continue

            if bgp.enabled is True:
                counts["bgp_enabled"] += 1

            counts["peer_groups"] += len(bgp.peer_groups)
            counts["peers"] += sum(
                len(group.peers) for group in bgp.peer_groups
            )
            counts["import_rules"] += len(bgp.import_rules)
            counts["export_rules"] += len(bgp.export_rules)
            counts["redistribution_rules"] += len(
                bgp.redistribution_rules
            )

    return counts


def _check_counts(
    source: Counter[str],
    parsed: Counter[str],
) -> int:
    mismatches = 0

    fields = (
        "firewalls",
        "subnet_records",
        "static_routes",
        "interface_addresses",
        "virtual_routers",
        "bgp_enabled",
        "peer_groups",
        "peers",
        "import_rules",
        "export_rules",
        "redistribution_rules",
        "redistribution_profiles",
        "collection_failures",
    )

    for field in fields:
        matches = source[field] == parsed[field]
        log = logger.info if matches else logger.error

        log(
            "Parser record count checked",
            extra={
                "record_type": field,
                "source_count": source[field],
                "parsed_count": parsed[field],
                "check_status": "OK" if matches else "MISMATCH",
            },
        )

        if not matches:
            mismatches += 1

    return mismatches


def _log_issues(
    result: PanoramaInventoryResult,
    limit: int,
) -> None:
    severities = Counter(issue.severity for issue in result.issues)

    logger.info(
        "Parsing issue summary",
        extra={
            "info_count": severities["info"],
            "warning_count": severities["warning"],
            "error_count": severities["error"],
        },
    )

    # Show errors first if the output is limited.
    priority = {"error": 0, "warning": 1, "info": 2}
    issues = sorted(
        result.issues,
        key=lambda issue: priority[issue.severity],
    )
    visible = issues if limit == 0 else issues[:limit]

    methods = {
        "info": logger.info,
        "warning": logger.warning,
        "error": logger.error,
    }

    for issue in visible:
        methods[issue.severity](
            "Panorama parsing issue",
            extra={
                "firewall_serial": issue.firewall_serial,
                "json_path": issue.path,
                "reason": issue.reason,
            },
        )

    if len(visible) < len(issues):
        logger.warning(
            "Additional parsing issues omitted",
            extra={"omitted_count": len(issues) - len(visible)},
        )


def _log_firewall(
    firewall: FirewallInventory,
    show_peers: bool,
    show_prefixes: bool,
) -> None:
    identity = {
        "firewall_name": firewall.hostname,
        "firewall_serial": firewall.serial,
    }
    management = firewall.management
    ha = firewall.ha
    status = firewall.collection_status

    logger.info(
        "Firewall inventory",
        extra={
            **identity,
            "management_ip": (
                str(management.ip_address)
                if management and management.ip_address is not None
                else None
            ),
            "management_prefix_length": (
                management.prefix_length if management else None
            ),
            "management_gateway": (
                str(management.default_gateway)
                if management and management.default_gateway is not None
                else None
            ),
            "management_dhcp": (
                management.is_dhcp if management else None
            ),
            "ha_enabled": ha.enabled if ha else None,
            "ha_local_state": ha.local_state if ha else None,
            "ha_peer_serial": ha.peer_serial if ha else None,
            "ha_config_sync": ha.config_sync if ha else None,
            "static_route_count": len(firewall.static_routes),
            "interface_address_count": len(
                firewall.interface_addresses
            ),
            "virtual_router_count": (
                len(firewall.virtual_routers)
                if firewall.virtual_routers is not None
                else None
            ),
            "collection_status": {
                "subnets": status.subnets,
                "management": status.management,
                "ha": status.ha,
                "virtual_routers": status.virtual_routers,
            },
        },
    )

    for router in firewall.virtual_routers or ():
        bgp = router.bgp

        logger.info(
            "Virtual-router configuration",
            extra={
                **identity,
                "virtual_router": router.name,
                "interfaces": list(router.interfaces),
                "bgp_present": bgp.present if bgp else None,
                "bgp_enabled": bgp.enabled if bgp else None,
                "local_as": bgp.local_as if bgp else None,
                "router_id": (
                    str(bgp.router_id)
                    if bgp and bgp.router_id is not None
                    else None
                ),
                "peer_group_count": (
                    len(bgp.peer_groups) if bgp else None
                ),
                "peer_count": (
                    sum(len(group.peers) for group in bgp.peer_groups)
                    if bgp else None
                ),
                "import_rule_count": (
                    len(bgp.import_rules) if bgp else None
                ),
                "export_rule_count": (
                    len(bgp.export_rules) if bgp else None
                ),
                "redistribution_profile_names": [
                    profile.name
                    for profile in router.redistribution_profiles
                ],
            },
        )

        if not show_peers or bgp is None:
            continue

        for group in bgp.peer_groups:
            for peer in group.peers:
                logger.info(
                    "Configured BGP peer",
                    extra={
                        **identity,
                        "virtual_router": router.name,
                        "bgp_enabled": bgp.enabled,
                        "local_as": bgp.local_as,
                        "peer_group": group.name,
                        "peer_group_type": group.type,
                        "peer_group_enabled": group.enabled,
                        "peer_name": peer.name,
                        "peer_enabled": peer.enabled,
                        "peer_as": peer.peer_as,
                        "peer_address_ip": peer.peer_address_ip,
                        "peer_address_fqdn": peer.peer_address_fqdn,
                        "local_interface": peer.local_interface,
                        "local_address": peer.local_address,
                    },
                )

    if not show_prefixes:
        return

    for address in firewall.interface_addresses:
        logger.info(
            "Configured interface address",
            extra={
                **identity,
                "virtual_router": address.virtual_router,
                "interface": address.interface,
                "ip_address": (
                    str(address.ip_address)
                    if address.ip_address is not None
                    else None
                ),
                "prefix_length": address.prefix_length,
                "network": (
                    str(address.network)
                    if address.network is not None
                    else None
                ),
                "configured_value": address.configured_value,
            },
        )

    for route in firewall.static_routes:
        logger.info(
            "Configured static route",
            extra={
                **identity,
                "virtual_router": route.virtual_router,
                "route_name": route.route_name,
                "destination": (
                    str(route.destination)
                    if route.destination is not None
                    else None
                ),
                "interface": route.interface,
                "next_hop": route.next_hop,
                "configured_value": route.configured_value,
            },
        )


def _nonnegative_int(value: str) -> int:
    number = int(value)

    if number < 0:
        raise argparse.ArgumentTypeError(
            "Value must be zero or greater"
        )

    return number


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the Panorama inventory JSON parser."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to a Panorama inventory JSON export",
    )
    parser.add_argument(
        "--show-peers",
        action="store_true",
        help="Log every configured BGP peer",
    )
    parser.add_argument(
        "--show-prefixes",
        action="store_true",
        help="Log every interface address and static route",
    )
    parser.add_argument(
        "--issue-limit",
        type=_nonnegative_int,
        default=30,
        help="Maximum individual parsing issues to log; 0 shows all",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    level = "DEBUG" if args.debug else "INFO"
    log_path = Path("logs/check_panorama_inventory.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

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
                    "file_path": str(log_path),
                },
            ])
        )
    )

    try:
        raw_text = args.file.read_text(encoding="utf-8-sig")
        source = json.loads(raw_text)

        if not isinstance(source, dict):
            raise ValueError("Expected a JSON object at the report root")

        result = parse_panorama_inventory(raw_text)
    except (OSError, UnicodeError, ValueError) as exc:
        logger.error(
            "Panorama inventory could not be read",
            extra={
                "input_file": str(args.file),
                "reason": str(exc),
            },
        )
        return 1

    logger.info(
        "Panorama collection metadata",
        extra={
            "input_file": str(args.file),
            "schema_version": result.schema_version,
            "panorama": result.panorama,
            "collection_started_at_utc": (
                result.collection_started_at_utc.isoformat()
            ),
            "collected_at_utc": result.collected_at_utc.isoformat(),
            "panorama_connected": result.panorama_connected,
            "selected_connected": result.selected_connected,
            "selected_not_connected": list(
                result.selected_not_connected
            ),
        },
    )

    mismatches = _check_counts(
        _source_counts(source),
        _parsed_counts(result),
    )

    for failure in result.collection_failures:
        logger.error(
            "Collector reported a failure",
            extra={
                "firewall_name": failure.hostname,
                "firewall_serial": failure.serial,
                "collection_section": failure.section,
                "reason": failure.error,
            },
        )

    _log_issues(result, args.issue_limit)

    for firewall in result.firewalls:
        _log_firewall(
            firewall,
            show_peers=args.show_peers,
            show_prefixes=args.show_prefixes,
        )

    parsing_errors = sum(
        issue.severity == "error" for issue in result.issues
    )
    warnings = sum(
        issue.severity == "warning" for issue in result.issues
    )

    # A section can be incomplete even if failures[] is empty.
    incomplete_sections = 0

    for firewall in result.firewalls:
        status = firewall.collection_status
        states = [status.subnets, status.management, status.ha]

        if result.schema_version == "2.1":
            states.append(status.virtual_routers)

        incomplete_sections += sum(
            state != "success" for state in states
        )

    failed = bool(
        mismatches
        or parsing_errors
        or result.collection_failures
        or incomplete_sections
    )

    log = logger.error if failed else logger.info
    log(
        "Panorama inventory check completed",
        extra={
            "check_status": (
                "FAILED"
                if failed
                else "PASSED_WITH_WARNINGS"
                if warnings
                else "PASSED"
            ),
            "firewall_count": len(result.firewalls),
            "count_mismatches": mismatches,
            "parsing_errors": parsing_errors,
            "parsing_warnings": warnings,
            "collection_failures": len(result.collection_failures),
            "incomplete_sections": incomplete_sections,
            "log_file": str(log_path),
        },
    )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
