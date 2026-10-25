"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..base import Base, RelationMixin

class InterfacePrefix(RelationMixin, Base):
    __tablename__ = 'interface_prefixes'
    interface_id: Mapped[str] = mapped_column(String(36), ForeignKey('interfaces.id'))
    prefix_id: Mapped[str] = mapped_column(String(36), ForeignKey('network_prefixes.id'))
