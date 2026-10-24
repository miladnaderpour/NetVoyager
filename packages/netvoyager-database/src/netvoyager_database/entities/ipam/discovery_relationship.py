
"""SQLAlchemy persistence for prefix discovery relationships."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from netvoyager_database.entities.base import Base, TimestampMixin


class PrefixDiscoveryRelationshipEntity(Base, TimestampMixin):
    """Persist a non-destructive relationship between prefix candidates."""

    __tablename__ = "prefix_discovery_relationships"

    __table_args__ = (
        CheckConstraint(
            "candidate_a_id != candidate_b_id",
            name="distinct_candidates",
        ),
        CheckConstraint(
            "status IN ('possible', 'confirmed', 'rejected')",
            name="valid_status",
        ),
        CheckConstraint(
            "candidate_a_id < candidate_b_id",
            name="ordered_pair",
        ),
        UniqueConstraint(
            "candidate_a_id",
            "candidate_b_id",
            name="unique_candidate_pair",
        ),
    )

    relationship_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    candidate_a_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prefix_discovery_candidates.candidate_id"),
        nullable=False,
        index=True,
    )

    candidate_b_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prefix_discovery_candidates.candidate_id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
