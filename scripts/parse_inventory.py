"""Parse and inspect a network device inventory file.

Read device observations from an Excel inventory, convert suitable
observations into NetworkDevice objects, record supporting evidence,
and report import and analysis results to console and file.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.devices.processing import process_device_observations
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import read_network_devices
from netvoyager_analysis.devices.scopes import build_site_scopes



logger = get_logger("scripts.parse_inventory")


def main() -> None:
    """Read an Excel inventory and report import and analysis results."""
    parser = argparse.ArgumentParser(
        description="Check network device inventory parsing and analysis.",
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the network device inventory Excel file.",
    )
    parser.add_argument(
        "--sheet",
        help="Worksheet name. Uses the active sheet when omitted.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and individual observation/device output.",
    )

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    level = "DEBUG" if args.debug else "INFO"
    log_path = Path(f"logs/inventory_{timestamp}.log")
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

    source = str(args.file.resolve())

    logger.info("Source: %s", source)

    if args.sheet is not None:
        logger.info("Worksheet: %s", args.sheet)

    try:
        result = read_network_devices(
            args.file,
            sheet_name=args.sheet,
        )
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot read inventory: {exc}")

    logger.info(
        "Inventory parsed: observations=%d, issues=%d, "
        "management_ips=%d",
        len(result.observations),
        len(result.issues),
        len(result.ip_sites_mapping),
    )

    for observation in result.observations:
        logger.debug(
            "Observation: row=%s | name=%s | host_name=%s | "
            "site=%s | role=%s | management_ip=%s | "
            "primary_IPv4=%s | manufacturer=%s | model=%s | "
            "serial_number=%s | asset_tag=%s | "
            "software_version=%s | status=%s",
            observation.line_number,
            observation.name,
            observation.host_name,
            observation.site,
            observation.role,
            observation.management_ip,
            observation.primary_IPv4,
            observation.manufacturer,
            observation.model,
            observation.serial_number,
            observation.asset_tag,
            observation.software_version,
            observation.status,
        )

        logger.debug(
            "Raw observation: row=%s | %s",
            observation.line_number,
            observation.raw_line,
        )

    if result.issues:
        logger.warning(
            "Inventory issues detected: %d",
            len(result.issues),
        )

        for issue in result.issues:
            logger.warning(
                "Issue: row=%d | %s",
                issue.row_number,
                issue.reason,
            )
    else:
        logger.info("No inventory issues detected.")

    multi_site_ips = {
        address: sites
        for address, sites in result.ip_sites_mapping.items()
        if len(sites) > 1
    }

    logger.info(
        "Management IP mappings: total=%d, multi_site=%d",
        len(result.ip_sites_mapping),
        len(multi_site_ips),
    )

    for address, sites in multi_site_ips.items():
        logger.warning(
            "Management IP mapped to multiple sites: %s | sites=%s",
            address,
            ", ".join(sorted(sites)),
        )

    context: dict[str, object] = {}

    if args.sheet is not None:
        context["sheet"] = args.sheet

    evidence_store = EvidenceStore()

    devices = process_device_observations(
        result.observations,
        source=source,
        evidence_store=evidence_store,
        context=context,
    )

    logger.info(
        "Device analysis: devices=%d, evidence_records=%d, "
        "evidence_relations=%d",
        len(devices),
        len(evidence_store.records),
        len(evidence_store.relations),
    )

    for device in devices:
        logger.debug(
            "Device: id=%s | name=%s | host_name=%s | "
            "site=%s | role=%s | management_ip=%s | "
            "primary_IPv4=%s | manufacturer=%s | model=%s | "
            "serial_number=%s | asset_tag=%s | "
            "software_version=%s | status=%s",
            device.device_id,
            device.name,
            device.host_name,
            device.site,
            device.role,
            device.management_ip,
            device.primary_IPv4,
            device.manufacturer,
            device.model,
            device.serial_number,
            device.asset_tag,
            device.software_version,
            device.status,
        )

    unresolved_count = (
        len(result.observations) - len(devices)
    )

    logger.info(
        "Analysis validation: observations=%d, devices=%d, "
        "unresolved=%d",
        len(result.observations),
        len(devices),
        unresolved_count,
    )

    if len(evidence_store.records) != len(result.observations):
        logger.warning(
            "Evidence record count does not match observation count: "
            "observations=%d, evidence_records=%d",
            len(result.observations),
            len(evidence_store.records),
        )

    if len(evidence_store.relations) != len(devices):
        logger.warning(
            "Evidence relation count does not match device count: "
            "devices=%d, evidence_relations=%d",
            len(devices),
            len(evidence_store.relations),
        )

    logger.info("Log file: %s", log_path.resolve())

    site_scopes = build_site_scopes(devices)

    logger.info(
        "Site scope analysis: sites=%d, assigned_devices=%d, "
        "unassigned_devices=%d",
        len(site_scopes),
        sum(len(scope.devices) for scope in site_scopes.values()),
        len(devices) - sum(
            len(scope.devices)
            for scope in site_scopes.values()
        ),
    )

    for scope in site_scopes.values():
        logger.debug(
            "Site scope: id=%s | devices=%d",
            scope.scope_id,
            len(scope.devices),
        )


if __name__ == "__main__":
    main()