"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..base import Base, new_id, now_utc

class EntityEvent(Base):
    """Append-only audit record; application must never update or delete."""
    __tablename__ = 'entity_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_kind: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    event_type: Mapped[str] = mapped_column(String(80))
    previous_state_id: Mapped[str | None] = mapped_column(String(36))
    new_state_id: Mapped[str | None] = mapped_column(String(36))
    from_type: Mapped[str | None] = mapped_column(String(20))
    to_type: Mapped[str | None] = mapped_column(String(20))
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('sources.id'))
    observation_id: Mapped[str | None] = mapped_column(String(36))
    actor_type: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
