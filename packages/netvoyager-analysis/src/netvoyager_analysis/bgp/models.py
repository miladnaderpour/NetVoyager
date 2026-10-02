"""BGP analysis results linking network records to source evidence."""

from dataclasses import dataclass, field
from uuid import UUID

from netvoyager_network.bgp.models import AsPrefix

from ..evidence.models import EvidenceRecord


@dataclass(frozen=True, slots=True)
class EvidencedAsPrefix:
    """One AS prefix record linked to its source observation.

    record is constructed directly from a parsed route. evidence_id
    identifies the evidence created for that same route occurrence.

    Separate observations remain separate entries, even when their
    AsPrefix values are identical.
    """

    record: AsPrefix
    evidence_id: UUID


@dataclass(slots=True)
class BgpRouteProcessingResult:
    """Network records and evidence created from parsed BGP routes.

    records contains one EvidencedAsPrefix for each route with a nonempty
    AS path. Each record references evidence included in this result.

    evidence contains one EvidenceRecord per input route occurrence,
    including routes with empty or unavailable AS paths.

    unknown_origin_evidence_ids references the evidence for routes that
    could not produce an AsPrefix. No placeholder origin ASN is created.

    Each collection preserves input encounter order among its entries.
    Duplicate route occurrences are retained.

    Processing does not group prefixes, create autonomous systems, or
    establish scope associations. The caller supplies routes from one
    intended routing context and retains a separate result for each context.

    Type annotations describe expected values. This model does not perform
    runtime validation or enforce reference consistency.
    """

    records: tuple[EvidencedAsPrefix, ...] = field(
        default_factory=tuple,
    )
    evidence: tuple[EvidenceRecord, ...] = field(
        default_factory=tuple,
    )
    unknown_origin_evidence_ids: tuple[UUID, ...] = field(
        default_factory=tuple,
    )