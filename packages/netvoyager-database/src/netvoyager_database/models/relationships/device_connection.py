"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..base import Base, RelationMixin

class DeviceConnection(RelationMixin, Base):
    __tablename__ = 'device_connections'
    __table_args__ = (
        CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_device_connection_record_type'),
        CheckConstraint('device_a_id < device_b_id', name='ck_device_connection_order'),
        CheckConstraint("record_type != 'canonical' OR relation_type IS NOT NULL", name='ck_device_connection_canonical_type'),
        Index('uq_canonical_device_connection', 'device_a_id', 'device_b_id', 'relation_type', unique=True, sqlite_where=text("record_type = 'canonical'")),
    )
    device_a_id: Mapped[str] = mapped_column(String(36), ForeignKey('devices.id'))
    device_b_id: Mapped[str] = mapped_column(String(36), ForeignKey('devices.id'))
