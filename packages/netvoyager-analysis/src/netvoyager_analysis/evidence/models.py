"""Evidence models for network observations and analysis findings.

Evidence preserves source context and evaluated values without modifying
network objects or independently validating network associations.

Callers provide correctly typed, JSON-compatible values. These models
do not perform runtime validation or serialization.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from netvoyager_core.types import JsonValue


@dataclass(frozen=True, slots=True)
class EvidenceSubject:
    """Identify a network entity addressed by an evidence record.

    kind identifies the entity category, such as "prefix", "device",
    "asn", or "scope".

    identifier contains its textual identity:
    - Prefix: canonical CIDR notation.
    - Device: the string representation of device_id.
    - ASN: the decimal ASN.
    - Scope: scope_id.

    context qualifies an identity when necessary, such as the device and
    virtual router in which a prefix was observed. Missing context remains
    unknown; a bare prefix does not establish a global routing identity.

    Field reassignment is prevented, but nested context values remain
    mutable. Treat them as snapshots after construction.
    """

    kind: str
    identifier: str
    context: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """Identify the artifact or analysis operation that produced evidence.

    kind describes the source category, such as "bgp_local_rib",
    "panorama_export", "device_inventory", or "analysis".

    reference identifies a specific source artifact or analysis run.
    A filename alone does not distinguish versions of the same file.

    locator identifies a position within the source, such as a sheet and
    row, line number, configuration path, or analysis function and version.
    Routing context belongs on subjects; collection time belongs on the
    evidence record.

    Field reassignment is prevented, but nested locator values remain
    mutable. Treat them as snapshots after construction.
    """

    kind: str
    reference: str
    locator: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceRecord:
    """One source observation or derived network analysis finding.

    kind defines the record's meaning. Producers define the required
    subjects and details for each kind.

    subjects identifies the entities involved. details preserves evaluated
    values, comparison relationships, and relevant analysis parameters.

    source identifies the artifact or operation that produced this record.
    observed_at is the source collection time when known, not the time
    NetVoyager processed it. A derived finding may leave it unset and
    reference collection times through its input evidence.

    created_at records evidence creation time and defaults to UTC.
    Supplied timestamps should be timezone-aware.

    based_on references evidence used to derive a finding. Direct source
    observations normally have no dependencies.

    Preserve evidence_id when saving and restoring records. The owning
    collection checks ID uniqueness, dependency existence, and cycles.

    Treat this record and its nested values as snapshots after creation.
    Immutability is a caller convention. Producers must copy mutable
    input values before storing them.

    Accepting a proposed network association is a separate decision from
    recording its supporting or conflicting evidence.
    """

    kind: str
    subjects: tuple[EvidenceSubject, ...]
    source: EvidenceSource

    evidence_id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
    )
    observed_at: datetime | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        kw_only=True,
    )
    details: dict[str, JsonValue] = field(default_factory=dict)
    based_on: tuple[UUID, ...] = field(default_factory=tuple)