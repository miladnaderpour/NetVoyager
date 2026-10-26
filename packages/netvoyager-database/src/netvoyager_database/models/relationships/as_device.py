"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..base import Base, RelationMixin

class ASDevice(RelationMixin, Base):
    __tablename__ = 'as_devices'
    __table_args__ = (CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_as_devices_record_type'), Index('uq_as_devices_canonical', 'as_id', 'device_id', 'relation_type', unique=True, sqlite_where=text("record_type = 'canonical'")), CheckConstraint("record_type != 'canonical' OR relation_type IS NOT NULL", name='ck_as_devices_canonical_relation_type'),)
    as_id: Mapped[str] = mapped_column(String(36), ForeignKey('autonomous_systems.id'))
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey('devices.id'))
