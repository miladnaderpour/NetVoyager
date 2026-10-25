"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def new_id() -> str:
    return str(uuid4())

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class InventoryRecord:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)
    state_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id)
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('sources.id'))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __mapper_args__ = {'eager_defaults': True}

class RelationMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(20), default='observed')
    relation_type: Mapped[str | None] = mapped_column(String(80))
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('sources.id'))
