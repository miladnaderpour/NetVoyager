"""Undirected interface-to-interface connectivity (ordered endpoint IDs)."""
from __future__ import annotations
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column
from ..base import Base, RelationMixin

class InterfaceConnection(RelationMixin, Base):
    __tablename__ = 'interface_connections'
    __table_args__ = (
        CheckConstraint("record_type IN ('observation','candidate','canonical')", name='ck_interface_connection_record_type'),
        CheckConstraint('interface_a_id < interface_b_id', name='ck_interface_connection_order'),
        CheckConstraint("record_type != 'canonical' OR relation_type IS NOT NULL", name='ck_interface_connection_canonical_type'),
        Index('uq_canonical_interface_connection', 'interface_a_id', 'interface_b_id', 'relation_type', unique=True, sqlite_where=text("record_type = 'canonical'")),
    )
    interface_a_id: Mapped[str] = mapped_column(String(36), ForeignKey('interfaces.id'), nullable=False)
    interface_b_id: Mapped[str] = mapped_column(String(36), ForeignKey('interfaces.id'), nullable=False)
