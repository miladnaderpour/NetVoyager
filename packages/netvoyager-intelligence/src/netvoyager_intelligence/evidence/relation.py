
"""SQLAlchemy model for evidence-to-object provenance relationships.

Evidence relations associate source observations with UUID-identified
domain objects without establishing operational domain relationships.
"""

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from netvoyager_intelligence.base import IntelligenceBase
from netvoyager_intelligence.evidence.record import EvidenceRecord


class EvidenceRelation(IntelligenceBase):
    """Associate one evidence record with one domain object.

    An evidence record may support multiple domain objects, and each
    domain object may have multiple independent evidence records.

    The evidence ID references an existing EvidenceRecord through a
    database foreign key.

    The object ID is a UUID identifying a domain object. Object type
    provides an additional safeguard without requiring foreign keys
    to individual domain tables.

    The composite primary key prevents duplicate evidence associations.
    """

    __tablename__ = "evidence_relations"

    __table_args__ = (
        Index(
            "ix_evidence_relations_object_id",
            "object_id",
        ),
    )

    evidence_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "evidence_records.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )

    object_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    object_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    evidence: Mapped["EvidenceRecord"] = relationship(
        "EvidenceRecord",
        back_populates="relations",
    )

    def __init__(
        self,
        evidence_id: UUID,
        object_type: str,
        object_id: UUID,
    ) -> None:
        """Initialize an evidence association with a domain object."""
        self.evidence_id = evidence_id
        self.object_type = object_type
        self.object_id = object_id
