"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .base import Base, InventoryRecord, new_id, now_utc

class Location(InventoryRecord, Base):
    __tablename__ = 'locations'
    __table_args__ = (
        CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_location_record_type'),
        CheckConstraint("record_type != 'canonical' OR (code IS NOT NULL AND length(trim(code)) > 0)", name='ck_canonical_location_code'),
        CheckConstraint("parent_location_id IS NULL OR parent_location_id != id", name='ck_location_not_self_parent'),
        Index('uq_canonical_location_code', 'code', unique=True, sqlite_where=text("record_type = 'canonical'")),
    )
    code: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str | None] = mapped_column(String(255))
    location_type: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    parent_location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('locations.id'))
