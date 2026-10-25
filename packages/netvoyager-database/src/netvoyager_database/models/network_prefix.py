"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .base import Base, InventoryRecord, new_id, now_utc

class NetworkPrefix(InventoryRecord, Base):
    __tablename__ = 'network_prefixes'
    __table_args__ = (CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_prefix_record_type'),)
    cidr: Mapped[str] = mapped_column(String(50))
    address_space_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('address_spaces.id'))
    vrf: Mapped[str | None] = mapped_column(String(255))
    vlan: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
