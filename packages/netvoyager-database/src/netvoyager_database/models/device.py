"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .base import Base, InventoryRecord, new_id, now_utc

class Device(InventoryRecord, Base):
    __tablename__ = 'devices'
    __table_args__ = (CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_device_record_type'), CheckConstraint("device_type IN ('physical','logical')", name='ck_device_type'),)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False, default='physical')
    logical_key: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    hostname: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255), index=True)
    management_ip: Mapped[str | None] = mapped_column(String(45))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(80))
    asset_tag: Mapped[str | None] = mapped_column(String(255))
    software_version: Mapped[str | None] = mapped_column(String(255))
