"""Central ORM audit, immutability and state-version enforcement.

The ORM layer cannot authenticate actors: callers must supply a verified actor
through session.info (usually via UnitOfWork). Hooks do not authorize changes.
"""
from __future__ import annotations

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from .models.base import InventoryRecord, RelationMixin, new_id
from .models.history.entity_event import EntityEvent


class InventoryStateError(Exception):
    def __init__(self, message: str, *, code: str = "storage.immutable_state_violation") -> None:
        super().__init__(message)
        self.code, self.message = code, message
        self.details: dict[str, object] = {}


_BOOKKEEPING = frozenset({"state_id", "last_seen", "updated_at", "first_seen", "created_at"})


def _kind(obj):
    return {'network_prefixes': 'network_prefix', 'autonomous_systems': 'autonomous_system'}.get(obj.__tablename__, obj.__tablename__[:-1])


def _actor(session):
    context = session.info.get('netvoyager_actor')
    if not isinstance(context, dict) or context.get('actor_type') not in ('human', 'system', 'ai_agent') or not str(context.get('actor_id') or '').strip():
        raise InventoryStateError('Authenticated actor context required for audited mutation', code='storage.audit_actor_required')
    return context


def _snapshot_changes(obj):
    state = inspect(obj)
    before, after = {}, {}
    for prop in state.mapper.column_attrs:
        name = prop.key
        if name in _BOOKKEEPING:
            continue
        history = state.attrs[name].history
        if not history.has_changes():
            continue
        # SQLAlchemy tracks original scalar values when loaded through ORM.
        previous = history.deleted[0] if history.deleted else None
        current = history.added[0] if history.added else getattr(obj, name)
        if previous != current:
            before[name], after[name] = previous, current
    return before, after


def _event(session, obj, *, event_type, before, after, old_state=None, new_state=None, old_type=None):
    ctx = _actor(session)
    session.add(EntityEvent(
        entity_kind=_kind(obj), entity_id=obj.id,
        event_type=event_type,
        from_type=old_type, to_type=obj.record_type,
        previous_state_id=old_state, new_state_id=new_state,
        actor_type=ctx['actor_type'], actor_id=ctx['actor_id'],
        source_id=ctx.get('source_id'), observation_id=ctx.get('observation_id'),
        reason=ctx.get('reason'), before=before, after=after,
    ))


@event.listens_for(Session, 'before_flush')
def _guard_inventory_state(session: Session, flush_context, instances) -> None:
    # Explicit lifecycle helpers own the audit event for these objects on this flush.
    manual = session.info.pop('netvoyager_manual_audit', set())
    for obj in list(session.deleted):
        if isinstance(obj, (EntityEvent, InventoryRecord, RelationMixin)):
            raise InventoryStateError('Audited inventory rows cannot be deleted; retire them through a tracked state change')
    for obj in list(session.dirty):
        if isinstance(obj, EntityEvent):
            if any(inspect(obj).attrs[p.key].history.has_changes() for p in inspect(obj).mapper.column_attrs):
                raise InventoryStateError('Audit events cannot be modified')
            continue
        if not isinstance(obj, (InventoryRecord, RelationMixin)):
            continue
        before, after = _snapshot_changes(obj)
        if obj.record_type == 'observation' or before.get('record_type') == 'observation':
            if before:
                raise InventoryStateError('Persisted observations are immutable')
            continue
        if not after:
            continue
        if id(obj) in manual:
            continue
        old = inspect(obj).attrs.state_id.history.deleted
        previous_state = old[0] if old else obj.state_id
        if not inspect(obj).attrs.state_id.history.has_changes():
            obj.state_id = new_id()
        previous_type = before.get('record_type')
        _event(session, obj, event_type=('candidate_promoted' if previous_type == 'candidate' and obj.record_type == 'canonical' else 'relationship_updated' if isinstance(obj, RelationMixin) else 'attributes_updated'),
               before=before, after=after, old_state=previous_state, new_state=obj.state_id, old_type=previous_type)
    for obj in list(session.new):
        if isinstance(obj, (InventoryRecord, RelationMixin)) and id(obj) not in manual:
            # Defaults may not yet have been populated before flush.
            if obj.id is None:
                obj.id = new_id()
            if obj.state_id is None:
                obj.state_id = new_id()
            values = {p.key: getattr(obj, p.key) for p in inspect(obj).mapper.column_attrs if p.key not in _BOOKKEEPING and getattr(obj,p.key) is not None}
            _event(session, obj, event_type=f'{obj.record_type}_created', before=None, after=values, new_state=obj.state_id)
