"""Validate domain-dependent ORM relationships before database writes.

Database FK/check constraints still enforce structural validity.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session

from .device import Device
from .relationships.device_connection import DeviceConnection


def _device(session: Session, device_id: str) -> Device | None:
    for item in session.new:
        if isinstance(item, Device) and item.id == device_id:
            return item
    return session.get(Device, device_id)


@event.listens_for(Session, "before_flush")
def _validate_membership(session: Session, flush_context, instances) -> None:
    """Require each member_of link to pair exactly one logical and one physical device."""
    for link in session.new.union(session.dirty):
        if not isinstance(link, DeviceConnection) or link.relation_type != "member_of":
            continue
        a = _device(session, link.device_a_id)
        b = _device(session, link.device_b_id)
        if a is None or b is None or {a.device_type, b.device_type} != {"logical", "physical"}:
            raise ValueError("member_of requires one logical and one physical device")
