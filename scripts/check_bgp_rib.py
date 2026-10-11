"""Check Palo Alto BGP parsing and BGP analysis processing.

Validate the complete BGP flow:

Palo Alto local RIB
    -> parse_loc_rib()

Palo Alto BGP summary
    -> parse_bgp_summary()
    -> local ASN

Parsed routes + local ASN
    -> process_bgp_routes()
    -> AsPrefix
    -> AutonomousSystem
    -> Evidence

The script does not create NetworkPrefix objects or perform site analysis.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.bgp.processing import process_bgp_routes
from netvoyager_analysis.ipam.processing import (
    process_network_prefixes,
)
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_paloalto.bgp.parser import (
    parse_bgp_summary,
    parse_loc_rib,
)
from netvoyager_analysis.ipam.store import NetworkPrefixStore

logger = get_logger(
    "scripts.check_bgp_rib"
)


def _select_router(
    routers,
    name: str | None,
):
    """Select exactly one virtual-router section.

    Automatically select the only section when the input contains one
    virtual router.

    When multiple sections exist, require the caller to identify the
    desired virtual router explicitly.
    """
    if name is None:
        if len(routers) == 1:
            return routers[0]

        available = ", ".join(
            router.virtual_router
            for router in routers
        )

        raise ValueError(
            "Multiple virtual-router sections were found. "
            "Use --virtual-router to select one. "
            f"Available: {available}"
        )

    matches = [
        router
        for router in routers
        if router.virtual_router == name
    ]

    if len(matches) == 1:
        return matches[0]

    available = ", ".join(
        router.virtual_router
        for router in routers
    )

    raise ValueError(
        f"Virtual router {name!r} was not found uniquely. "
        f"Available: {available}"
    )


def _resolve_local_asn(
    *,
    manual_local_asn: int | None,
    summary_path: Path | None,
    encoding: str,
    virtual_router: str,
) -> tuple[int | None, str]:
    """Resolve the local ASN from manual input or BGP summary.

    Explicit manual input takes precedence over the summary file.

    Return the resolved ASN and a short description of its source.
    """
    if manual_local_asn is not None:
        return (
            manual_local_asn,
            "manual",
        )

    if summary_path is None:
        return (
            None,
            "not supplied",
        )

    try:
        summary_text = summary_path.read_text(
            encoding=encoding
        )
    except (
        OSError,
        UnicodeError,
        LookupError,
    ) as exc:
        raise ValueError(
            f"Cannot read BGP summary file: {exc}"
        ) from exc

    summary = parse_bgp_summary(
        summary_text
    )

    if summary.virtual_router != virtual_router:
        raise ValueError(
            "BGP summary virtual router does not match "
            "the selected local-RIB virtual router: "
            f"{summary.virtual_router!r} != {virtual_router!r}"
        )

    return (
        summary.local_asn,
        "BGP summary",
    )


def _log_local_as_prefixes(
    result,
) -> None:
    """Log AsPrefix objects created from local BGP routes."""
    local_prefixes = []

    for as_prefix in result.as_prefixes:
        if as_prefix.as_path == ():
            local_prefixes.append(
                as_prefix
            )

    logger.info(
        "Local AsPrefix observations",
        extra={
            "count": len(
                local_prefixes
            )
        },
    )

    for as_prefix in local_prefixes:
        logger.info(
            "Local AsPrefix",
            extra={
                "prefix": str(
                    as_prefix.prefix
                ),
                "asn": as_prefix.asn,
                "as_path": list(
                    as_prefix.as_path
                ),
                "id": str(
                    as_prefix.id
                ),
            },
        )


def _log_autonomous_systems(
    result,
) -> None:
    """Log a compact summary of generated autonomous systems."""
    logger.info(
        "Autonomous systems",
        extra={
            "count": len(
                result.autonomous_systems
            )
        },
    )

    for autonomous_system in result.autonomous_systems:
        logger.debug(
            "Autonomous system",
            extra={
                "asn": autonomous_system.asn,
                "prefix_count": len(
                    autonomous_system.prefixes
                ),
                "id": str(
                    autonomous_system.id
                ),
            },
        )


def main() -> None:
    """Run the Palo Alto BGP processing integration check."""
    parser = argparse.ArgumentParser(
        description=__doc__,
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
        help=(
            "Optional path to Palo Alto "
            "`show routing protocol bgp summary` output."
        ),
    )

    parser.add_argument(
        "--local-asn",
        type=int,
        help=(
            "Explicit local ASN. "
            "Overrides the ASN parsed from --summary."
        ),
    )

    parser.add_argument(
        "--virtual-router",
        help=(
            "Virtual-router name to process when the RIB "
            "contains multiple sections."
        ),
    )

    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help=(
            "Input text encoding "
            "(default: utf-8-sig)."
        ),
    )

    parser.add_argument(
        "--show-local-routes",
        action="store_true",
        help=(
            "Log local BGP routes and their resulting "
            "AsPrefix records."
        ),
    )

    parser.add_argument(
        "--show-autonomous-systems",
        action="store_true",
        help=(
            "Log generated AutonomousSystem objects "
            "at DEBUG level."
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
        f"logs/check_bgp_rib_{timestamp}.log"
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

    logger.info(
        "BGP RIB source",
        extra={
            "source": str(
                args.rib.resolve()
            )
        },
    )

    try:
        rib_text = args.rib.read_text(
            encoding=args.encoding
        )
    except (
        OSError,
        UnicodeError,
        LookupError,
    ) as exc:
        parser.error(
            f"Cannot read BGP RIB file: {exc}"
        )

    try:
        rib_dump = parse_loc_rib(
            rib_text
        )
    except ValueError as exc:
        parser.error(
            str(exc)
        )

    logger.info(
        "BGP RIB sections found",
        extra={
            "section_count": len(
                rib_dump.routers
            )
        },
    )

    try:
        router = _select_router(
            rib_dump.routers,
            args.virtual_router,
        )
    except ValueError as exc:
        parser.error(
            str(exc)
        )

    logger.info(
        "BGP router section selected",
        extra={
            "virtual_router": (
                router.virtual_router
            ),
            "virtual_router_id": (
                router.virtual_router_id
            ),
            "parsed_routes": len(
                router.routes
            ),
            "reported_routes": (
                router.total_routes_shown
            ),
            "unparsed_lines": len(
                router.unparsed_lines
            ),
        },
    )

    try:
        local_asn, local_asn_source = (
            _resolve_local_asn(
                manual_local_asn=(
                    args.local_asn
                ),
                summary_path=args.summary,
                encoding=args.encoding,
                virtual_router=(
                    router.virtual_router
                ),
            )
        )
    except ValueError as exc:
        parser.error(
            str(exc)
        )

    logger.info(
        "Local ASN resolved",
        extra={
            "local_asn": local_asn,
            "source": local_asn_source,
        },
    )

    evidence_store = EvidenceStore()

    result = process_bgp_routes(
        router.routes,
        source=str(
            args.rib.resolve()
        ),
        evidence_store=evidence_store,
        local_asn=local_asn,
        context={
            "virtual_router": (
                router.virtual_router
            ),
            "virtual_router_id": (
                router.virtual_router_id
            ),
        },
    )

    unique_as_prefix_networks = {
        as_prefix.prefix
        for as_prefix in result.as_prefixes
    }

    autonomous_system_asns = {
        autonomous_system.asn
        for autonomous_system
        in result.autonomous_systems
    }

    logger.info(
        "BGP processing result",
        extra={
            "parsed_routes": len(
                router.routes
            ),
            "as_prefix_observations": len(
                result.as_prefixes
            ),
            "unique_as_prefix_networks": len(
                unique_as_prefix_networks
            ),
            "autonomous_systems": len(
                result.autonomous_systems
            ),
            "local_routes": (
                result.local_route_count
            ),
            "unknown_origins": (
                result.unknown_origin_count
            ),
            "local_asn": local_asn,
            "local_asn_present_in_output": (
                local_asn
                in autonomous_system_asns
                if local_asn is not None
                else False
            ),
        },
    )

    logger.info(
        "Evidence result",
        extra={
            "records": len(
                evidence_store.records
            ),
            "relations": len(
                evidence_store.relations
            ),
        },
    )

    if args.show_local_routes:
        _log_local_as_prefixes(
            result
        )

    if args.show_autonomous_systems:
        _log_autonomous_systems(
            result
        )

    if (
        local_asn is not None
        and result.unknown_origin_count == 0
        and len(result.as_prefixes)
        == len(router.routes)
    ):
        logger.info(
            "BGP processing validation PASSED",
            extra={
                "routes": len(
                    router.routes
                ),
                "as_prefixes": len(
                    result.as_prefixes
                ),
            },
        )

    else:
        logger.warning(
            "BGP processing validation requires review",
            extra={
                "routes": len(
                    router.routes
                ),
                "as_prefixes": len(
                    result.as_prefixes
                ),
                "unknown_origins": (
                    result.unknown_origin_count
                ),
                "local_asn": local_asn,
            },
        )

    network_prefix_store = NetworkPrefixStore()

    network_prefixes = process_network_prefixes(
        result.as_prefixes,
        network_prefix_store=network_prefix_store,
        evidence_store=evidence_store,
    )

    logger.info(
        "IPAM prefix processing result",
        extra={
            "as_prefix_observations": len(
                result.as_prefixes
            ),
            "network_prefixes": len(
                network_prefixes
            ),
            "network_prefix_store": len(
                network_prefix_store
            ),
            "evidence_records": len(
                evidence_store.records
            ),
            "evidence_relations": len(
                evidence_store.relations
            ),
        },
    )

    logger.info(
        "Log file",
        extra={
            "path": str(
                log_path.resolve()
            )
        },
    )


if __name__ == "__main__":
    main()