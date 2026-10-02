"""Create AS prefix records and evidence directly from parsed BGP routes."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from uuid import UUID

from netvoyager_core.logging import get_logger
from netvoyager_core.types import JsonValue
from netvoyager_network.bgp.models import AsPrefix

from ..evidence.bgp import (
    build_bgp_route_evidence_record,
    get_origin_asn,
)
from ..evidence.models import EvidenceRecord, EvidenceSource
from ..evidence.protocols import BgpRouteObservation
from .models import BgpRouteProcessingResult, EvidencedAsPrefix


logger = get_logger("analysis.bgp.processing")


def process_bgp_routes(
    routes: Iterable[BgpRouteObservation],
    *,
    source: EvidenceSource,
    context: Mapping[str, JsonValue],
    observed_at: datetime | None = None,
) -> BgpRouteProcessingResult:
    """Create AS prefix records and linked evidence from parsed routes.

    Consume the iterable once, preserving encounter order and duplicate
    occurrences. Do not modify input routes or metadata.

    For a known origin, construct AsPrefix directly from the route, then
    create its evidence and link the two through EvidencedAsPrefix.
    Origin attribution uses the same helper as the evidence builder.

    For an empty or unavailable AS path, create evidence only and retain
    its ID in unknown_origin_evidence_ids. No local or placeholder ASN
    is inferred.

    The producer supplies validated BgpRouteObservation values. The source
    and context apply to every supplied route, so the caller must separate
    unrelated routing contexts before processing.

    observed_at is the known collection time, or None when unknown.
    Empty input produces empty result collections.

    This function does not filter records, group prefixes, create AS
    objects, or establish scope associations. Debug logs report batch
    boundaries and individual processing outcomes.
    """
    logger.debug(
        "Starting BGP route processing",
        extra={
            "source_reference": source.reference,
            "routing_context": dict(context),
        },
    )

    records: list[EvidencedAsPrefix] = []
    evidence_records: list[EvidenceRecord] = []
    unknown_origin_ids: list[UUID] = []
    empty_path_count = 0
    unavailable_path_count = 0

    for route_index, route in enumerate(routes, start=1):
        as_path = route.as_path
        origin_asn = get_origin_asn(as_path)
        prefix_record: AsPrefix | None = None

        if origin_asn is not None:
            prefix_record = AsPrefix(
                asn=origin_asn,
                prefix=route.prefix,
                as_path=as_path,
            )
        elif as_path is None:
            unavailable_path_count += 1
        else:
            empty_path_count += 1

        route_evidence = build_bgp_route_evidence_record(
            route,
            source=source,
            context=context,
            observed_at=observed_at,
        )
        evidence_records.append(route_evidence)

        if prefix_record is None:
            unknown_origin_ids.append(route_evidence.evidence_id)
        else:
            records.append(
                EvidencedAsPrefix(
                    record=prefix_record,
                    evidence_id=route_evidence.evidence_id,
                )
            )

        logger.debug(
            "BGP route processed",
            extra={
                "route_index": route_index,
                "evidence_id": str(route_evidence.evidence_id),
                "prefix": str(route.prefix),
                "asn": origin_asn,
                "prefix_record_created": prefix_record is not None,
            },
        )

    result = BgpRouteProcessingResult(
        records=tuple(records),
        evidence=tuple(evidence_records),
        unknown_origin_evidence_ids=tuple(unknown_origin_ids),
    )

    logger.debug(
        "BGP route processing completed",
        extra={
            "source_reference": source.reference,
            "routing_context": dict(context),
            "route_count": len(result.evidence),
            "prefix_record_count": len(result.records),
            "unknown_origin_count": len(unknown_origin_ids),
            "empty_path_count": empty_path_count,
            "unavailable_path_count": unavailable_path_count,
        },
    )

    return result