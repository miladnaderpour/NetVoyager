"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .base import Base, InventoryRecord, new_id, now_utc
from .device import Device

class Interface(InventoryRecord, Base):
    __tablename__ = 'interfaces'
    __table_args__ = (
        CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_interface_record_type'),
        CheckConstraint("record_type != 'canonical' OR device_id IS NOT NULL", name='ck_canonical_interface_device'),
        Index('uq_canonical_device_interface_name', 'device_id', 'name', unique=True, sqlite_where=text("record_type = 'canonical'")),
    )
    device_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('devices.id'))
    name: Mapped[str] = mapped_column(String(255))
    mac_address: Mapped[str | None] = mapped_column(String(32))
    interface_type: Mapped[str | None] = mapped_column(String(80))
