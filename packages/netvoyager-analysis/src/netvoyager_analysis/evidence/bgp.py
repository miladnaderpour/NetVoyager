"""Build vendor-neutral evidence from parsed IPv4 BGP observations."""

from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import datetime

from netvoyager_core.logging import get_logger
from netvoyager_core.types import JsonValue

from .models import EvidenceRecord, EvidenceSource, EvidenceSubject
from .protocols import BgpRouteObservation


logger = get_logger("analysis.evidence.bgp")


def get_origin_asn(as_path: tuple[int, ...] | None) -> int | None:
    """Attribute an origin using the last element of an ordered AS path.

    Empty and unavailable paths return None. No local ASN is inferred.
    The producer must supply a validated ordered sequence; this helper
    does not interpret vendor syntax or unordered AS sets.
    """
    return as_path[-1] if as_path else None


def build_bgp_route_evidence_record(
    route: BgpRouteObservation,
    *,
    source: EvidenceSource,
    context: Mapping[str, JsonValue],
    observed_at: datetime | None = None,
) -> EvidenceRecord:
    """Create evidence for one parsed BGP route occurrence.

    Include a context-qualified prefix subject and, for a nonempty AS
    path, an origin ASN subject. Origin attribution uses get_origin_asn().

    Preserve next hop, peer, AS path, raw line, and origin attribution
    details using JSON-compatible values. Empty and unavailable paths
    remain distinct as [] and None.

    Deep-copy routing context and the source locator. Replace its
    line_number with the route's value, or omit it when unavailable.
    Preserve all other locator entries.

    observed_at is the known source collection time, or None when unknown.
    The record receives a new evidence ID and has no based_on dependencies.

    Input values are not modified. This operation records an observation;
    it does not validate ownership, select a path, or assign scopes.

    Emit one debug message identifying the created record. Raw source text
    remains in evidence and is not included in the log message.
    """
    as_path = route.as_path
    origin_asn = get_origin_asn(as_path)

    subjects = [
        EvidenceSubject(
            kind="prefix",
            identifier=str(route.prefix),
            context=deepcopy(dict(context)),
        ),
    ]

    if origin_asn is not None:
        subjects.append(
            EvidenceSubject(
                kind="asn",
                identifier=str(origin_asn),
            )
        )

    locator = deepcopy(source.locator)
    locator.pop("line_number", None)

    if route.line_number is not None:
        locator["line_number"] = route.line_number

    details: dict[str, JsonValue] = {
        "next_hop": (
            str(route.next_hop)
            if route.next_hop is not None
            else None
        ),
        "peer": route.peer,
        "as_path": (
            [asn for asn in as_path]
            if as_path is not None
            else None
        ),
        "raw_line": route.raw_line,
        "origin_asn": origin_asn,
        "origin_method": (
            "last_as_path_element"
            if origin_asn is not None
            else None
        ),
    }

    record = EvidenceRecord(
        kind="bgp.prefix_observed",
        subjects=tuple(subjects),
        source=EvidenceSource(
            kind=source.kind,
            reference=source.reference,
            locator=locator,
        ),
        observed_at=observed_at,
        details=details,
    )

    logger.debug(
        "BGP route evidence created",
        extra={
            "evidence_id": str(record.evidence_id),
            "source_reference": source.reference,
            "line_number": route.line_number,
            "prefix": str(route.prefix),
            "origin_asn": origin_asn,
            "as_path_state": (
                "unavailable"
                if as_path is None
                else "populated" if as_path else "empty"
            ),
        },
    )

    return record


def build_bgp_route_evidence(
    routes: Iterable[BgpRouteObservation],
    *,
    source: EvidenceSource,
    context: Mapping[str, JsonValue],
    observed_at: datetime | None = None,
) -> tuple[EvidenceRecord, ...]:
    """Create evidence for a batch of routes from one routing context.

    Consume the iterable once, preserving encounter order and duplicate
    occurrences. Empty input returns an empty tuple.

    Delegate each observation to build_bgp_route_evidence_record().
    No AsPrefix objects are created by this evidence-only operation.

    Log batch start and completion at DEBUG level. The single-record
    builder logs individual evidence creation.
    """
    logger.debug(
        "Starting BGP route evidence creation",
        extra={
            "source_reference": source.reference,
            "routing_context": dict(context),
        },
    )

    records = tuple(
        build_bgp_route_evidence_record(
            route,
            source=source,
            context=context,
            observed_at=observed_at,
        )
        for route in routes
    )

    logger.debug(
        "BGP route evidence creation completed",
        extra={
            "source_reference": source.reference,
            "routing_context": dict(context),
            "evidence_count": len(records),
        },
    )

    return records