"""Test Panorama firewall matching against inventory devices."""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.devices.matching import match_devices
from netvoyager_analysis.devices.processing import process_device_observations
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_analysis.paloalto.adapters import adapt_panorama_firewall
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import read_network_devices
from netvoyager_paloalto.inventory.parser import parse_panorama_inventory


logger = get_logger("netvoyager.scripts.test_panorama_device_matching")


def main() -> None:
    """Match Panorama firewalls against devices imported from Excel."""
    parser = argparse.ArgumentParser(
        description=(
            "Test Panorama firewall matching against the master inventory."
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
        help="Path to the Panorama inventory JSON file.",
    )
    parser.add_argument(
        "--sheet",
        help="Inventory worksheet name. Uses the active sheet when omitted.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    level = "DEBUG" if args.debug else "INFO"
    log_path = Path(
        f"logs/panorama_device_matching_{timestamp}.log"
    )
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

    inventory_source = str(args.inventory.resolve())
    panorama_source = str(args.panorama.resolve())

    logger.info("Inventory source: %s", inventory_source)
    logger.info("Panorama source: %s", panorama_source)

    if args.sheet is not None:
        logger.info("Inventory worksheet: %s", args.sheet)

    #
    # Read inventory.
    #
    try:
        inventory_result = read_network_devices(
            args.inventory,
            sheet_name=args.sheet,
        )
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot read inventory: {exc}")

    logger.info(
        "Inventory parsed: observations=%d, issues=%d",
        len(inventory_result.observations),
        len(inventory_result.issues),
    )

    #
    # Create baseline NetworkDevice objects.
    #
    evidence_store = EvidenceStore()

    inventory_context: dict[str, object] = {}

    if args.sheet is not None:
        inventory_context["sheet"] = args.sheet

    devices = process_device_observations(
        inventory_result.observations,
        source=inventory_source,
        evidence_store=evidence_store,
        context=inventory_context,
    )

    logger.info(
        "Inventory devices created: devices=%d",
        len(devices),
    )

    #
    # Read Panorama JSON.
    #
    try:
        raw_panorama = args.panorama.read_text(
            encoding="utf-8-sig",
        )
    except OSError as exc:
        parser.error(f"Cannot read Panorama file: {exc}")

    try:
        panorama_result = parse_panorama_inventory(raw_panorama)
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(f"Cannot parse Panorama inventory: {exc}")

    logger.info(
        "Panorama parsed: firewalls=%d, issues=%d, failures=%d",
        len(panorama_result.firewalls),
        len(panorama_result.issues),
        len(panorama_result.collection_failures),
    )

    #
    # Adapt Panorama firewall records to generic device identities.
    #
    panorama_observations = tuple(
        adapt_panorama_firewall(firewall)
        for firewall in panorama_result.firewalls
    )

    logger.info(
        "Panorama device identities created: %d",
        len(panorama_observations),
    )

    #
    # Match Panorama observations to inventory devices.
    #
    matching_result = match_devices(
        panorama_observations,
        devices,
    )

    method_counts = Counter(
        match.matched_by
        for match in matching_result.matches
    )

    logger.info(
        "Matching summary: firewalls=%d, matched=%d, unresolved=%d",
        len(panorama_observations),
        len(matching_result.matches),
        len(matching_result.unresolved),
    )

    for method, count in sorted(method_counts.items()):
        logger.info(
            "Match method: %s=%d",
            method,
            count,
        )

    #
    # Log successful matches.
    #
    for match in matching_result.matches:
        observation = match.observation

        logger.info(
            "MATCH: panorama_name=%s | serial=%s | "
            "management_ip=%s | device=%s | site=%s | "
            "device_id=%s | matched_by=%s",
            observation.host_name or observation.name,
            observation.serial_number,
            observation.management_ip,
            match.device.name,
            match.device.site,
            match.device.device_id,
            match.matched_by,
        )

    #
    # Log unresolved observations.
    #
    for unresolved in matching_result.unresolved:
        observation = unresolved.observation

        logger.warning(
            "UNRESOLVED: panorama_name=%s | serial=%s | "
            "management_ip=%s | reason=%s | candidates=%d",
            observation.host_name or observation.name,
            observation.serial_number,
            observation.management_ip,
            unresolved.reason,
            len(unresolved.candidates),
        )

        for candidate in unresolved.candidates:
            logger.warning(
                "  CANDIDATE: name=%s | host_name=%s | "
                "site=%s | serial=%s | management_ip=%s | "
                "device_id=%s",
                candidate.name,
                candidate.host_name,
                candidate.site,
                candidate.serial_number,
                candidate.management_ip,
                candidate.device_id,
            )

    logger.info("Log file: %s", log_path.resolve())


if __name__ == "__main__":
    main()