
"""SQLAlchemy model for evidence provenance records.

Evidence records preserve source observations without performing domain
matching, reconciliation, or attribute inference.

Each record has an independent UUID and may be associated with multiple
domain objects through EvidenceRelation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import TypeAlias
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from netvoyager_intelligence.base import IntelligenceBase

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .relation import EvidenceRelation


JsonValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)


class EvidenceRecord(IntelligenceBase):
    """Preserve an individual observation and its source provenance.

    Each record represents one observation, independently of whether
    another record contains identical source data.

    Details contain JSON-compatible values and are retained for
    provenance inspection, not attribute searching or matching.

    Identity and creation time are assigned before database persistence,
    allowing evidence to be referenced within the same transaction.
    """

    __tablename__ = "evidence_records"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    details: Mapped[dict[str, JsonValue]] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    relations: Mapped[list["EvidenceRelation"]] = relationship(
        "EvidenceRelation",
        back_populates="evidence",
    )

    def __init__(
        self,
        source: str,
        details: dict[str, JsonValue],
        *,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Initialize a provenance record with identity and timestamp."""
        self.source = source
        self.details = details
        self.id = id if id is not None else uuid4()
        self.created_at = (
            created_at
            if created_at is not None
            else datetime.now(timezone.utc)
        )
