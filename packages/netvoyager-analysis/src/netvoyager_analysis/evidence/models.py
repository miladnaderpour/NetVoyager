"""Evidence records and their links to network objects."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Evidence with a source, native Python values, and creation time.

    Fields cannot be reassigned, but details remains a mutable dictionary.
    Treat its contents as unchanged after adding the record to a store.
    """

    source: str
    details: dict[str, object]
    id: UUID = field(default_factory=uuid4, kw_only=True)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        kw_only=True,
    )


@dataclass(frozen=True, slots=True)
class EvidenceRelation:
    """Link one evidence record to one network object."""

    evidence_id: UUID
    object_type: str
    object_id: UUID | str