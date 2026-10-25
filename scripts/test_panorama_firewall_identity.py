"""Test Panorama firewall identity resolution against inventory devices."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.devices.legacy_processing import process_device_observations
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_analysis.findings.store import FindingStore
from netvoyager_analysis.paloalto.processing import resolve_firewall_identities
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import read_network_devices
from netvoyager_paloalto.inventory.parser import parse_panorama_inventory


logger = get_logger(
    "netvoyager.scripts.test_panorama_firewall_identity"
)


def main() -> None:
    """Test Panorama firewall identity resolution."""
    parser = argparse.ArgumentParser(
        description=(
            "Test Panorama firewall identity resolution "
            "against the network device inventory."
        ),
    )

    parser.add_argument(
        "inventory",
        type=Path,
        help="Path to the network device inventory Excel file.",
    )

    parser.add_argument(
        "panorama",
        type=Path,
        help="Path to the Panorama inventory JSON export.",
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
        help="Panorama JSON encoding (default: utf-8-sig).",
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
        f"logs/panorama_firewall_identity_{timestamp}.log"
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

    panorama_source = str(
        args.panorama.resolve()
    )

    logger.info(
        "Inventory source: %s",
        inventory_source,
    )

    logger.info(
        "Panorama source: %s",
        panorama_source,
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
    # Shared stores.
    #
    evidence_store = EvidenceStore()
    finding_store = FindingStore()

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
    # Read Panorama JSON.
    #
    try:
        raw_panorama = args.panorama.read_text(
            encoding=args.encoding,
        )
    except (
        OSError,
        UnicodeError,
        LookupError,
    ) as exc:
        parser.error(
            f"Cannot read Panorama inventory: {exc}"
        )

    #
    # Parse Panorama inventory.
    #
    try:
        panorama_result = parse_panorama_inventory(
            raw_panorama
        )
    except ValueError as exc:
        parser.error(
            f"Cannot parse Panorama inventory: {exc}"
        )

    logger.info(
        "Panorama parsed: firewalls=%d, issues=%d, failures=%d",
        len(panorama_result.firewalls),
        len(panorama_result.issues),
        len(panorama_result.collection_failures),
    )

    #
    # Resolve Panorama firewall identities.
    #
    resolutions = resolve_firewall_identities(
        panorama_result.firewalls,
        devices,
        finding_store=finding_store,
    )

    #
    # Resolution summary.
    #
    status_counts = Counter(
        resolution.status
        for resolution in resolutions
    )

    match_method_counts = Counter(
        resolution.matched_by
        for resolution in resolutions
        if resolution.matched_by is not None
    )

    logger.info(
        "Resolution totals: firewalls=%d, statuses=%s",
        len(resolutions),
        dict(status_counts),
    )

    logger.info(
        "Match methods: %s",
        dict(match_method_counts),
    )

    #
    # Finding summary.
    #
    finding_counts = Counter(
        finding.kind
        for finding in finding_store.findings
    )

    logger.info(
        "Finding totals: total=%d, kinds=%s",
        len(finding_store.findings),
        dict(finding_counts),
    )

    #
    # Detailed firewall resolution results.
    #
    for resolution in resolutions:
        logger.info(
            "FIREWALL: "
            "hostname=%s | "
            "serial=%s | "
            "status=%s | "
            "matched_by=%s | "
            "device=%s | "
            "device_serial=%s | "
            "device_id=%s | "
            "identity_scope=%s",
            resolution.firewall.hostname,
            resolution.firewall.serial,
            resolution.status,
            resolution.matched_by,
            (
                resolution.device.name
                if resolution.device is not None
                else None
            ),
            (
                resolution.device.serial_number
                if resolution.device is not None
                else None
            ),
            (
                resolution.device.device_id
                if resolution.device is not None
                else None
            ),
            resolution.identity_scope_id,
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
    # Evidence summary.
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