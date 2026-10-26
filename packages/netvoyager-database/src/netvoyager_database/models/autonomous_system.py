"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .base import Base, InventoryRecord, new_id, now_utc

class AutonomousSystem(InventoryRecord, Base):
    __tablename__ = 'autonomous_systems'
    __table_args__ = (
        CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_as_record_type'),
        CheckConstraint('asn BETWEEN 0 AND 4294967295', name='ck_asn_range'),
        Index('uq_canonical_asn', 'asn', unique=True, sqlite_where=text("record_type = 'canonical'")),
    )
    asn: Mapped[int] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String(255))
