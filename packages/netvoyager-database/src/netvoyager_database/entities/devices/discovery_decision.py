
"""SQLAlchemy entity for device-discovery decision history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from netvoyager_database.entities.base import Base, pk_uuid


class DeviceDiscoveryDecisionEntity(Base):
    """Persist an immutable discovery decision as an audit record.

    A database-owned UUID identifies the audit row independently of
    the candidate or relationship whose state was changed.

    The repository is responsible for append-only access.
    """

    __tablename__ = "device_discovery_decisions"

    __table_args__ = (
        CheckConstraint(
            "decision_type IN ("
            "'relationship_status', 'candidate_resolution', "
            "'candidate_lifecycle', 'candidate_attributes'"
            ")",
            name="valid_discovery_decision_type",
        ),
        CheckConstraint(
            "subject_type IN ('candidate', 'relationship')",
            name="valid_discovery_decision_subject_type",
        ),
        CheckConstraint(
            "actor_type IN ('human', 'system', 'ai_agent')",
            name="valid_discovery_decision_actor_type",
        ),
        Index(
            "ix_device_discovery_decisions_subject",
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
        nullable=True,
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
        nullable=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    method: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    policy_version: Mapped[int | None] = mapped_column(
        nullable=True,
    )
