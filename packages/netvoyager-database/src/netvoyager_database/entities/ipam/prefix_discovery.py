
"""Persistence for independent prefix observations and discovery candidates."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from netvoyager_database.entities.base import Base, TimestampMixin


class PrefixObservationEntity(Base):
    """Store one source observation without asserting canonical acceptance."""

    __tablename__ = "prefix_observations"

    __table_args__ = (
        Index(
            "ix_prefix_observations_dataset_ref",
            "dataset_id",
            "local_ref",
        ),
    )

    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    local_ref: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    prefix: Mapped[str] = mapped_column(
        String(49), nullable=False
    )
    observation_kind: Mapped[str] = mapped_column(
        String(80), nullable=False
    )
    routing_context: Mapped[str | None] = mapped_column(
        String(255)
    )
    address_space_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True)
    )
    local_device_ref: Mapped[str | None] = mapped_column(
        String(255)
    )


class PrefixDiscoveryCandidateEntity(Base, TimestampMixin):
    """Persist the current snapshot of a prefix discovery candidate."""

    __tablename__ = "prefix_discovery_candidates"

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'candidate', 'corroborated', 'resolved', "
            "'rejected', 'retired'"
            ")",
            name="valid_status",
        ),
        CheckConstraint(
            "(status = 'resolved' AND resolved_prefix_id IS NOT NULL) "
            "OR (status != 'resolved' AND resolved_prefix_id IS NULL)",
            name="valid_resolution",
        ),
        CheckConstraint(
            "last_seen >= first_seen",
            name="valid_seen_range",
        ),
        Index(
            "ix_prefix_discovery_candidates_lookup",
            "prefix",
            "address_space_id",
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    prefix: Mapped[str | None] = mapped_column(
        String(49)
    )
    address_space_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True)
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    resolved_prefix_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_prefixes.id"),
        nullable=True,
    )


class PrefixCandidateObservationEntity(Base):
    """Explicit association between an observation and a candidate."""

    __tablename__ = "prefix_candidate_observations"

    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prefix_observations.observation_id"),
        primary_key=True,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prefix_discovery_candidates.candidate_id"),
        primary_key=True,
    )
