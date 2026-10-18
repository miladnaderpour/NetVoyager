
"""Shared SQLAlchemy base, metadata conventions, and entity mixins.

Database-specific models inherit from Base and may opt into common
timestamp, soft-deletion, and UUID primary-key behavior.

Domain identity and lifecycle decisions remain outside this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all NetVoyager SQLAlchemy entities."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Provide creation and modification timestamps for an entity."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )


class SoftDeleteMixin:
    """Provide optional logical-deletion state for an entity."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


def pk_uuid():
    """Define a UUIDv4 primary key for database-owned identities.

    Do not use this helper for domain identities whose UUIDs are
    generated deterministically, such as NetworkDevice.device_id.
    """
    return mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
