
"""Create BGP prefix records, autonomous systems, and supporting evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)
from uuid import UUID

from netvoyager_core.logging import get_logger
from netvoyager_intelligence.evidence import EvidenceRecord
from netvoyager_intelligence.evidence.record import JsonValue
from netvoyager_network.bgp.grouping import group_as_prefixes
from netvoyager_network.bgp.models import (
    AsPrefix,
    AutonomousSystem,
)

from netvoyager_analysis.protocols.evidence import (
    EvidenceRepositoryProtocol,
)

from .models import BgpProcessingResult
from .protocols import BgpRouteObservation


logger = get_logger("analysis.bgp.processing")


def _is_local_route(
    route: BgpRouteObservation,
) -> bool:
    """Return whether a route is explicitly identified as local.

    An empty AS path alone does not establish local origin.
    """
    if route.peer is None:
        return False

    return route.peer.strip().casefold() == "local"


def _get_origin_asn(
    route: BgpRouteObservation,
    *,
    local_asn: int | None,
) -> int | None:
    """Determine the origin ASN for a BGP route observation.

    A populated AS path uses its final ASN as the origin.

    Explicitly local routes use local_asn when available.

    Routes without a usable AS path and without explicit local
    origin have an unknown origin ASN.
    """
    if route.as_path:
        return route.as_path[-1]

    if _is_local_route(route):
        return local_asn

    return None


def _json_compatible(
    value: object,
) -> JsonValue:
    """Convert supported observation values into JSON-compatible values.

    Preserve JSON scalars, normalize UUID and IP address/network
    objects to strings, and recursively convert mappings and sequences.

    Unsupported values are rejected rather than silently stringified.
    """
    if value is None:
        return None

    if isinstance(value, (str, bool, int, float)):
        return value

    if isinstance(
        value,
        (
            UUID,
            IPv4Address,
            IPv6Address,
            IPv4Network,
            IPv6Network,
        ),
    ):
        return str(value)

    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    "Evidence context keys must be strings"
                )

            result[key] = _json_compatible(item)

        return result

    if isinstance(value, (tuple, list)):
        return [
            _json_compatible(item)
            for item in value
        ]

    raise TypeError(
        "Unsupported evidence detail type: "
        f"{type(value).__name__}"
    )


def _create_route_evidence(
    route: BgpRouteObservation,
    *,
    source: str,
    origin_asn: int | None,
    is_local_route: bool,
    context: Mapping[str, object] | None,
) -> EvidenceRecord:
    """Create JSON-compatible evidence for one BGP route observation."""
    details: dict[str, JsonValue] = {
        "prefix": str(route.prefix),
        "origin_asn": origin_asn,
        "as_path": (
            list(route.as_path)
            if route.as_path is not None
            else None
        ),
        "next_hop": (
            str(route.next_hop)
            if route.next_hop is not None
            else None
        ),
        "peer": route.peer,
        "is_local_route": is_local_route,
        "line": route.line_number,
        "raw_line": route.raw_line,
        "context": _json_compatible(
            context if context is not None else {}
        ),
    }

    return EvidenceRecord(
        source=source,
        details=details,
    )


def _link_autonomous_system_evidence(
    observed_evidence: Iterable[tuple[AsPrefix, UUID]],
    *,
    autonomous_systems: Mapping[int, AutonomousSystem],
    evidence_store: EvidenceRepositoryProtocol,
) -> None:
    """Link route evidence to the corresponding autonomous system."""
    for as_prefix, evidence_id in observed_evidence:
        autonomous_system = autonomous_systems[as_prefix.asn]

        evidence_store.link(
            evidence_id,
            "autonomous_system",
            autonomous_system.id,
        )


def process_bgp_routes(
    routes: Iterable[BgpRouteObservation],
    *,
    source: str,
    source_id: UUID,
    evidence_store: EvidenceRepositoryProtocol,
    local_asn: int | None = None,
    context: Mapping[str, object] | None = None,
) -> BgpProcessingResult:
    """Create AsPrefix and AutonomousSystem objects from BGP observations.

    A route with a populated AS path uses the final ASN in that
    path as its origin ASN.

    A route explicitly identified as local uses local_asn when
    available.

    Routes without a usable origin ASN still create evidence,
    but do not create an AsPrefix.

    Preserve input encounter order and duplicate observations.
    Evidence is recorded for every supplied route.

    Database transactions are owned by the calling application.
    This function does not commit or roll back.
    """
    as_prefixes: list[AsPrefix] = []
    observed_evidence: list[tuple[AsPrefix, UUID]] = []

    local_route_count = 0
    unknown_origin_count = 0
    route_count = 0

    for route in routes:
        route_count += 1

        is_local_route = _is_local_route(route)

        if is_local_route:
            local_route_count += 1

        origin_asn = _get_origin_asn(
            route,
            local_asn=local_asn,
        )

        as_prefix: AsPrefix | None = None

        if origin_asn is not None:
            as_prefix = AsPrefix(
                source_id=source_id,
                asn=origin_asn,
                prefix=route.prefix,
                as_path=route.as_path,
            )

            as_prefixes.append(as_prefix)

        else:
            unknown_origin_count += 1

        evidence = _create_route_evidence(
            route,
            source=source,
            origin_asn=origin_asn,
            is_local_route=is_local_route,
            context=context,
        )

        evidence_store.add(evidence)

        if as_prefix is not None:
            evidence_store.link(
                evidence.id,
                "as_prefix",
                as_prefix.id,
            )

            observed_evidence.append(
                (as_prefix, evidence.id)
            )

        logger.debug(
            "BGP route processed",
            extra={
                "prefix": str(route.prefix),
                "origin_asn": origin_asn,
                "is_local_route": is_local_route,
                "as_prefix_created": (
                    as_prefix is not None
                ),
                "evidence_id": str(evidence.id),
            },
        )

    grouping_result = group_as_prefixes(
        as_prefixes
    )

    _link_autonomous_system_evidence(
        observed_evidence,
        autonomous_systems=grouping_result.autonomous_systems,
        evidence_store=evidence_store,
    )

    autonomous_systems = tuple(
        grouping_result.autonomous_systems.values()
    )

    logger.info(
        "BGP processing completed",
        extra={
            "route_count": route_count,
            "as_prefix_count": len(as_prefixes),
            "autonomous_system_count": len(
                autonomous_systems
            ),
            "local_route_count": local_route_count,
            "unknown_origin_count": unknown_origin_count,
            "duplicate_prefix_count": len(
                grouping_result.duplicates
            ),
            "local_asn": local_asn,
        },
    )

    return BgpProcessingResult(
        as_prefixes=tuple(as_prefixes),
        autonomous_systems=autonomous_systems,
        local_route_count=local_route_count,
        unknown_origin_count=unknown_origin_count,
    )
