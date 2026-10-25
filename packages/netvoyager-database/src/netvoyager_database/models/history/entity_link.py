"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..base import Base, new_id, now_utc

class EntityLink(Base):
    """Polymorphic typed link for observation provenance/resolution."""
    __tablename__ = 'entity_links'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    from_kind: Mapped[str] = mapped_column(String(40))
    from_id: Mapped[str] = mapped_column(String(36))
    to_kind: Mapped[str] = mapped_column(String(40))
    to_id: Mapped[str] = mapped_column(String(36))
    relation: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint('from_kind','from_id','to_kind','to_id','relation',name='uq_entity_link'),)
