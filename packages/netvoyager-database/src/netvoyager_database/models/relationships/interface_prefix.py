"""SQLAlchemy 2.x ORM model; shared domain and database representation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..base import Base, RelationMixin

class InterfacePrefix(RelationMixin, Base):
    __tablename__ = 'interface_prefixes'
    __table_args__ = (CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_interface_prefixes_record_type'), Index('uq_interface_prefixes_canonical', 'interface_id', 'prefix_id', 'relation_type', unique=True, sqlite_where=text("record_type = 'canonical'")), CheckConstraint("record_type != 'canonical' OR relation_type IS NOT NULL", name='ck_interface_prefixes_canonical_relation_type'),)
    interface_id: Mapped[str] = mapped_column(String(36), ForeignKey('interfaces.id'))
    prefix_id: Mapped[str] = mapped_column(String(36), ForeignKey('network_prefixes.id'))
