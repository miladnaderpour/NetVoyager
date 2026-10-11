"""Create BGP prefix records, autonomous systems, and supporting evidence."""

from collections.abc import Iterable, Mapping
from uuid import UUID

from netvoyager_core.logging import get_logger
from netvoyager_network.bgp.grouping import group_as_prefixes
from netvoyager_network.bgp.models import (
    AsPrefix,
    AutonomousSystem,
)

from ..evidence.models import EvidenceRecord
from ..evidence.store import EvidenceStore
from .models import BgpProcessingResult
from .protocols import BgpRouteObservation


logger = get_logger(
    "analysis.bgp.processing"
)


def _is_local_route(
    route: BgpRouteObservation,
) -> bool:
    """Return whether the route is explicitly identified as local.

    Only the peer label is used to classify a route as local. An empty
    AS path alone does not imply that the route is locally originated.
    """
    if route.peer is None:
        return False

    return route.peer.strip().casefold() == "local"


def _get_origin_asn(
    route: BgpRouteObservation,
    *,
    local_asn: int | None,
) -> int | None:
    """Determine the origin ASN for one BGP route observation.

    A populated AS path uses its final ASN as the origin.

    A route explicitly identified as local uses local_asn when one was
    supplied.

    Routes with no usable AS path that are not local, and local routes
    processed without a local ASN, return None.
    """
    if route.as_path:
        return route.as_path[-1]

    if _is_local_route(route):
        return local_asn

    return None


def _create_route_evidence(
    route: BgpRouteObservation,
    *,
    source: str,
    origin_asn: int | None,
    is_local_route: bool,
    context: Mapping[str, object] | None,
) -> EvidenceRecord:
    """Create evidence for one parsed BGP route observation."""
    return EvidenceRecord(
        source=source,
        details={
            "prefix": route.prefix,
            "origin_asn": origin_asn,
            "as_path": route.as_path,
            "next_hop": route.next_hop,
            "peer": route.peer,
            "is_local_route": is_local_route,
            "line": route.line_number,
            "raw_line": route.raw_line,
            "context": (
                dict(context)
                if context is not None
                else {}
            ),
        },
    )


def _link_autonomous_system_evidence(
    as_prefixes: Iterable[AsPrefix],
    *,
    evidence_ids_by_prefix_id: Mapping[UUID, UUID],
    autonomous_systems: Mapping[int, AutonomousSystem],
    evidence_store: EvidenceStore,
) -> None:
    """Link route evidence to derived AutonomousSystem objects.

    Each AsPrefix created during BGP processing has one corresponding
    EvidenceRecord. Reuse that known relationship directly when linking
    evidence to the AutonomousSystem derived from the AsPrefix ASN.
    """
    for as_prefix in as_prefixes:
        autonomous_system = autonomous_systems[
            as_prefix.asn
        ]

        evidence_id = evidence_ids_by_prefix_id[
            as_prefix.id
        ]

        evidence_store.link(
            evidence_id,
            "autonomous_system",
            autonomous_system.id,
        )


def process_bgp_routes(
    routes: Iterable[BgpRouteObservation],
    *,
    source: str,
    evidence_store: EvidenceStore,
    local_asn: int | None = None,
    context: Mapping[str, object] | None = None,
) -> BgpProcessingResult:
    """Create AsPrefix and AutonomousSystem objects from parsed BGP routes.

    A route with a populated AS path uses the final ASN in that path as its
    origin ASN.

    A route explicitly identified as local uses local_asn as its origin ASN
    when local_asn is available. This allows locally originated routes with
    empty AS paths to participate in normal AsPrefix and AutonomousSystem
    processing.

    Routes without a usable origin ASN still create evidence but do not
    create an AsPrefix.

    Preserve input encounter order and duplicate route observations.
    Evidence is recorded for every supplied route.
    """
    as_prefixes: list[AsPrefix] = []

    evidence_ids_by_prefix_id: dict[
        UUID,
        UUID,
    ] = {}

    local_route_count = 0
    unknown_origin_count = 0
    route_count = 0

    for route in routes:
        route_count += 1

        is_local_route = _is_local_route(
            route
        )

        if is_local_route:
            local_route_count += 1

        origin_asn = _get_origin_asn(
            route,
            local_asn=local_asn,
        )

        as_prefix: AsPrefix | None = None

        if origin_asn is not None:
            as_prefix = AsPrefix(
                asn=origin_asn,
                prefix=route.prefix,
                as_path=route.as_path,
            )

            as_prefixes.append(
                as_prefix
            )

        else:
            unknown_origin_count += 1

        evidence = _create_route_evidence(
            route,
            source=source,
            origin_asn=origin_asn,
            is_local_route=is_local_route,
            context=context,
        )

        evidence_store.add(
            evidence
        )

        if as_prefix is not None:
            evidence_store.link(
                evidence.id,
                "as_prefix",
                as_prefix.id,
            )

            evidence_ids_by_prefix_id[
                as_prefix.id
            ] = evidence.id

        logger.debug(
            "BGP route processed",
            extra={
                "prefix": str(
                    route.prefix
                ),
                "origin_asn": origin_asn,
                "is_local_route": is_local_route,
                "as_prefix_created": (
                    as_prefix is not None
                ),
                "evidence_id": str(
                    evidence.id
                ),
            },
        )

    grouping_result = group_as_prefixes(
        as_prefixes
    )

    _link_autonomous_system_evidence(
        as_prefixes,
        evidence_ids_by_prefix_id=(
            evidence_ids_by_prefix_id
        ),
        autonomous_systems=(
            grouping_result.autonomous_systems
        ),
        evidence_store=evidence_store,
    )

    autonomous_systems = tuple(
        grouping_result.autonomous_systems.values()
    )

    logger.info(
        "BGP processing completed",
        extra={
            "route_count": route_count,
            "as_prefix_count": len(
                as_prefixes
            ),
            "autonomous_system_count": len(
                autonomous_systems
            ),
            "local_route_count": (
                local_route_count
            ),
            "unknown_origin_count": (
                unknown_origin_count
            ),
            "duplicate_prefix_count": len(
                grouping_result.duplicates
            ),
            "local_asn": local_asn,
        },
    )

    return BgpProcessingResult(
        as_prefixes=tuple(
            as_prefixes
        ),
        autonomous_systems=autonomous_systems,
        local_route_count=local_route_count,
        unknown_origin_count=unknown_origin_count,
    )