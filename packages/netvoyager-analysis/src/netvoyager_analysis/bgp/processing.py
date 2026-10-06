"""Create AS prefix records and store evidence from parsed BGP routes."""

from collections.abc import Iterable, Mapping

from netvoyager_core.logging import get_logger
from netvoyager_network.bgp.models import AsPrefix

from ..evidence.models import EvidenceRecord
from ..evidence.store import EvidenceStore
from .protocols import BgpRouteObservation


logger = get_logger("analysis.bgp.processing")


def process_bgp_routes(
    routes: Iterable[BgpRouteObservation],
    *,
    source: str,
    evidence_store: EvidenceStore,
    context: Mapping[str, object] | None = None,
) -> list[AsPrefix]:
    """Create prefixes and record evidence for each input route.

    Use the last ASN in a nonempty AS path as the origin. Routes with
    empty or unavailable paths produce evidence only.

    Preserve input order and duplicates. Store native Python values in
    evidence details, including optional routing context.
    """
    records: list[AsPrefix] = []
    unknown_origins = 0

    for route in routes:
        as_path = route.as_path
        origin_asn = as_path[-1] if as_path else None

        record = None
        if origin_asn is not None:
            record = AsPrefix(
                asn=origin_asn,
                prefix=route.prefix,
                as_path=as_path,
            )
            records.append(record)
        else:
            unknown_origins += 1

        evidence = EvidenceRecord(
            source=source,
            details={
                "prefix": route.prefix,
                "origin_asn": origin_asn,
                "as_path": as_path,
                "next_hop": route.next_hop,
                "peer": route.peer,
                "line": route.line_number,
                "raw_line": route.raw_line,
                "context": dict(context) if context is not None else {},
            },
        )
        evidence_store.add(evidence)

        if record is not None:
            evidence_store.link(
                evidence.id,
                "as_prefix",
                record.id,
            )

        logger.debug(
            "BGP route processed: prefix=%s, origin_asn=%s, evidence_id=%s",
            route.prefix,
            origin_asn,
            evidence.id,
        )

    logger.info(
        "BGP processing completed: prefixes=%d, unknown_origins=%d",
        len(records),
        unknown_origins,
    )

    return records