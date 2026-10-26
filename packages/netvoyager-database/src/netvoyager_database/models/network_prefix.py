"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from ipaddress import ip_network
from sqlalchemy.orm import validates
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .base import Base, InventoryRecord, new_id, now_utc

class NetworkPrefix(InventoryRecord, Base):
    __tablename__ = 'network_prefixes'
    __table_args__ = (
        CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_prefix_record_type'),
        CheckConstraint("record_type != 'canonical' OR address_space_id IS NOT NULL", name='ck_canonical_prefix_address_space'),
        CheckConstraint('vlan IS NULL OR (vlan BETWEEN 1 AND 4094)', name='ck_prefix_vlan'),
        Index('uq_canonical_prefix_address_space_cidr', 'address_space_id', 'cidr', unique=True, sqlite_where=text("record_type = 'canonical'")),
    )
    cidr: Mapped[str] = mapped_column(String(50))
    address_space_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('address_spaces.id'))
    vrf: Mapped[str | None] = mapped_column(String(255))
    vlan: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)

    @validates("cidr")
    def normalize_cidr(self, key: str, value: str) -> str:
        """Store IPv4/IPv6 CIDRs in canonical network notation.

        Network host bits are normalized; malformed addresses are rejected.
        """
        if not isinstance(value, str):
            raise ValueError("CIDR must be a string")
        return str(ip_network(value.strip(), strict=False))
