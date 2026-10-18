
"""SQLAlchemy entity for provisional network-device identities."""

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


class DeviceDiscoveryCandidateEntity(Base, TimestampMixin):
    """Persist one independent device-discovery candidate.

    Candidate identity is supplied by the domain model.

    This entity stores the current candidate snapshot. Supporting
    evidence, relationships, and decision history are persisted
    independently.
    """

    __tablename__ = "device_discovery_candidates"

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'candidate', 'corroborated', 'resolved', "
            "'rejected', 'retired'"
            ")",
            name="valid_candidate_status",
        ),
        CheckConstraint(
            "(status = 'resolved' AND resolved_device_id IS NOT NULL) "
            "OR (status != 'resolved' AND resolved_device_id IS NULL)",
            name="valid_candidate_resolution",
        ),
        CheckConstraint(
            "last_seen >= first_seen",
            name="valid_candidate_seen_range",
        ),
        Index(
            "ix_device_discovery_candidates_name",
            "name",
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="candidate",
    )

    name: Mapped[str | None] = mapped_column(String(255))
    host_name: Mapped[str | None] = mapped_column(String(255))

    serial_number: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )

    management_ip: Mapped[str | None] = mapped_column(
        String(45),
        index=True,
    )

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    resolved_device_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_devices.device_id"),
        nullable=True,
        index=True,
    )
