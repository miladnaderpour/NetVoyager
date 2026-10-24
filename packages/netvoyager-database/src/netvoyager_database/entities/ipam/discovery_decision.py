
"""SQLAlchemy persistence for prefix discovery decision history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    JSON,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from netvoyager_database.entities.base import Base, pk_uuid


class PrefixDiscoveryDecisionEntity(Base):
    """Store an append-only prefix discovery audit record.

    A decision records a previously authorized operation;
    it does not grant authorization.
    """

    __tablename__ = "prefix_discovery_decisions"

    __table_args__ = (
        CheckConstraint(
            "decision_type IN ("
            "'relationship_status', 'candidate_resolution', "
            "'candidate_lifecycle', 'candidate_attributes'"
            ")",
            name="valid_type",
        ),
        CheckConstraint(
            "subject_type IN ('candidate', 'relationship')",
            name="valid_subject_type",
        ),
        CheckConstraint(
            "actor_type IN ('human', 'system', 'ai_agent')",
            name="valid_actor_type",
        ),
        Index(
            "ix_prefix_discovery_decisions_subject",
            "subject_type",
            "subject_id",
            "timestamp",
        ),
    )

    decision_id: Mapped[UUID] = pk_uuid()

    decision_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    subject_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    subject_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    actor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    actor_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    previous_value: Mapped[str | None] = mapped_column(
        String,
    )

    new_value: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    evidence_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source_id: Mapped[str | None] = mapped_column(
        String(255),
    )

    method: Mapped[str | None] = mapped_column(
        String(100),
    )

    policy_version: Mapped[int | None] = mapped_column()
