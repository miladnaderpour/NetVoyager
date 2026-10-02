"""Parse a Palo Alto BGP local RIB file.

Read the supplied text file and log the number of parsed virtual-router
sections. Write logs to the console and a timestamped file.
"""

import argparse
from datetime import datetime
from pathlib import Path
import json
from hashlib import sha256

from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_analysis.bgp import (
    BgpRouteProcessingResult,
    process_bgp_routes,
)
from netvoyager_analysis.evidence import EvidenceSource
from netvoyager_network.bgp.grouping import group_as_prefixes
from netvoyager_network.bgp.models import AsGroupingResult

from netvoyager_paloalto.bgp import parse_loc_rib,BgpRibDump


from netvoyager_analysis.evidence import (
    EvidenceRecord,
    EvidenceSource,
    build_bgp_route_evidence,
)
from netvoyager_network.bgp.grouping import group_as_prefixes


logger = get_logger("scripts.paloalto_parse_rib")

def main() -> None:
    """Read the command-line input file and display parsing results."""
    parser = argparse.ArgumentParser(
        description="Check Palo Alto BGP local RIB parsing.",
    )

    parser.add_argument(
    "--debug",
    action="store_true",
    help="Enable debug logging.",
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

    logger.info(f"Source: {args.file}")
    logger.info(f"Virtual-router sections: {len(result.routers)}")

    if not result.routers:
        logger.warning("No virtual-router sections were parsed.")

    for res in result.routers:
        logger.info(f"Router: {res.virtual_router}, "
                    f"Prefixes: {len(res.routes)}")
        if len(res.routes) > 0:
            logger.info("   Routes:")
            logger.info("        |")
            for route in res.routes:
                logger.info(f"        +--> {route.prefix} -> {route.peer}        {route.as_path}")

    # Identify the parsed text content. This hashes decoded text, not file bytes.
    source_reference = (
        f"sha256-text:{sha256(raw_text.encode('utf-8')).hexdigest()}"
    )
    processed_by_section: dict[int, BgpRouteProcessingResult] = {}
    grouping_by_section: dict[int, AsGroupingResult] = {}

    for section_index, res in enumerate(result.routers, start=1):
        source = EvidenceSource(
            kind="bgp_local_rib",
            reference=source_reference,
            locator={
                "file_path": str(args.file.resolve()),
                "router_section_index": section_index,
            },
        )

        processed = process_bgp_routes(
            res.routes,
            source=source,
            context={
                "virtual_router": res.virtual_router,
                "virtual_router_id": res.virtual_router_id,
            },
            observed_at=None,
        )

        grouping = group_as_prefixes(
            item.record for item in processed.records
        )

        processed_by_section[section_index] = processed
        grouping_by_section[section_index] = grouping

        logger.info(
            "BGP routes processed and grouped",
            extra={
                "virtual_router": res.virtual_router,
                "route_count": len(processed.evidence),
                "prefix_record_count": len(processed.records),
                "unknown_origin_count": len(
                    processed.unknown_origin_evidence_ids
                ),
                "as_count": len(grouping.autonomous_systems),
                "duplicate_prefix_count": len(grouping.duplicates),
            },
        )


   



if __name__ == "__main__":
    main()