"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..base import Base, RelationMixin

class LocationDevice(RelationMixin, Base):
    __tablename__ = 'location_devices'
    __table_args__ = (CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_location_devices_record_type'), Index('uq_location_devices_canonical', 'location_id', 'device_id', 'relation_type', unique=True, sqlite_where=text("record_type = 'canonical'")), CheckConstraint("record_type != 'canonical' OR relation_type IS NOT NULL", name='ck_location_devices_canonical_relation_type'),)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey('locations.id'))
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey('devices.id'))
