"""Parse and analyze a Palo Alto BGP local RIB file.

Create AS prefix records, store their evidence, and group them by ASN
within each virtual-router section. Log results to console and file.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.bgp.processing import process_bgp_routes
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_network.bgp.grouping import group_as_prefixes
from netvoyager_paloalto.bgp import parse_loc_rib


logger = get_logger("scripts.paloalto_parse_rib")


def main() -> None:
    """Read a local RIB file and report processing and grouping results."""
    parser = argparse.ArgumentParser(
        description="Check Palo Alto BGP local RIB parsing.",
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the BGP local RIB text file.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Input text encoding (default: utf-8-sig).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and individual route output.",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    level = "DEBUG" if args.debug else "INFO"
    log_path = Path(f"logs/paloalto_rib_{timestamp}.log")
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
        raw_text = args.file.read_text(encoding=args.encoding)
    except (OSError, UnicodeError, LookupError) as exc:
        parser.error(f"Cannot read input file: {exc}")

    result = parse_loc_rib(raw_text)
    evidence_store = EvidenceStore()
    source = str(args.file.resolve())

    logger.info("Source: %s", source)
    logger.info("Virtual-router sections: %d", len(result.routers))

    if not result.routers:
        logger.warning("No virtual-router sections were parsed.")

    for section_index, router in enumerate(result.routers, start=1):
        logger.info(
            "Router: %s | Routes: %d",
            router.virtual_router,
            len(router.routes),
        )

        for route in router.routes:
            logger.debug(
                "Route: %s | Peer: %s | AS path: %s",
                route.prefix,
                route.peer,
                route.as_path,
            )

        records = process_bgp_routes(
            router.routes,
            source=source,
            evidence_store=evidence_store,
            context={
                "virtual_router": router.virtual_router,
                "virtual_router_id": router.virtual_router_id,
                "section_index": section_index,
            },
        )

        grouping = group_as_prefixes(records)

        logger.info(
            "Router %s: routes=%d, prefixes=%d, unknown_origins=%d, "
            "autonomous_systems=%d, duplicated_prefixes=%d",
            router.virtual_router,
            len(router.routes),
            len(records),
            len(router.routes) - len(records),
            len(grouping.autonomous_systems),
            len(grouping.duplicates),
        )

    logger.info(
        "Evidence totals: records=%d, relations=%d",
        len(evidence_store.records),
        len(evidence_store.relations),
    )
    logger.info("Log file: %s", log_path.resolve())


if __name__ == "__main__":
    main()