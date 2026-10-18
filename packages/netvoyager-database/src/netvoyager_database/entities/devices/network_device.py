
"""SQLAlchemy persistence model for canonical network devices."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from netvoyager_database.entities.base import Base, TimestampMixin


class NetworkDeviceEntity(Base, TimestampMixin):
    """Persist canonical network-device identity and technical attributes.

    The domain model owns deterministic UUIDv5 identity and state
    calculation. Database-specific revision and timestamp attributes
    do not participate in domain identity.
    """

    __tablename__ = "network_devices"

    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    role: Mapped[str | None] = mapped_column(String(255))
    site: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    primary_ipv4: Mapped[str | None] = mapped_column(String(45))
    management_ip: Mapped[str | None] = mapped_column(
        String(45),
        index=True,
    )
    host_name: Mapped[str | None] = mapped_column(String(255))

    virtual_chassis: Mapped[str | None] = mapped_column(String(255))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )
    status: Mapped[str | None] = mapped_column(String(100))
    asset_tag: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )
    software_version: Mapped[str | None] = mapped_column(String(255))

    integration_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    __mapper_args__ = {
        "version_id_col": revision,
    }
