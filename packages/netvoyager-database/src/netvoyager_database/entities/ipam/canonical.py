
"""Persistence entities for canonical address spaces and network prefixes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from netvoyager_database.entities.base import Base


class AddressSpaceEntity(Base):
    """Persist a stable, independently identified IP address space."""

    __tablename__ = "address_spaces"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )


class NetworkPrefixEntity(Base):
    """Persist one accepted CIDR within one address space."""

    __tablename__ = "network_prefixes"

    __table_args__ = (
        UniqueConstraint(
            "address_space_id",
            "prefix",
            name="unique_address_space_prefix",
        ),
        Index(
            "ix_network_prefixes_prefix",
            "prefix",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    address_space_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("address_spaces.id"),
        nullable=False,
    )
    prefix: Mapped[str] = mapped_column(
        String(49),
        nullable=False,
    )
