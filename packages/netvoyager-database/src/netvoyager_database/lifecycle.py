"""Experimental low-level mechanics; *caller* decides policy authorization.

This provides atomic mutation + history. Real application code must not
expose direct promotion to untrusted sources without an Analysis policy check.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from .models.base import new_id
from .models import EntityEvent, EntityLink

ALLOWED_KINDS = {'location', 'network_prefix', 'device', 'autonomous_system', 'interface'}


def _actor(actor_type, actor_id):
    if actor_type not in {'human','system','ai_agent'} or not actor_id or not actor_id.strip():
        raise ValueError('An identified human/system/ai_agent actor is required')


def record_creation(session: Session, *, kind: str, entity, actor_type: str, actor_id: str, source_id: str | None = None, observation_id: str | None = None):
    _actor(actor_type, actor_id)
    if kind not in ALLOWED_KINDS:
        raise ValueError('Invalid entity kind')
    session.info.setdefault("netvoyager_manual_audit", set()).add(id(entity))
    session.add(entity)
    session.flush()
    event = EntityEvent(entity_kind=kind, entity_id=entity.id, event_type=f'{entity.record_type}_created', to_type=entity.record_type, actor_type=actor_type, actor_id=actor_id, source_id=source_id, observation_id=observation_id, after={'record_type':entity.record_type})
    session.add(event)
    session.flush()
    return event


def link_observation(session: Session, *, kind: str, observation_id: str, entity_id: str, actor_type: str, actor_id: str):
    _actor(actor_type, actor_id)
    if kind not in ALLOWED_KINDS:
        raise ValueError('Invalid entity kind')
    link = EntityLink(from_kind=kind, from_id=observation_id, to_kind=kind, to_id=entity_id, relation='supports')
    session.add(link)
    session.add(EntityEvent(entity_kind=kind, entity_id=entity_id, event_type='observation_linked', observation_id=observation_id, actor_type=actor_type, actor_id=actor_id))
    session.flush()
    return link


def promote_candidate(session: Session, *, kind: str, entity, actor_type: str, actor_id: str, reason: str, observation_id: str | None = None):
    _actor(actor_type, actor_id)
    if kind not in ALLOWED_KINDS:
        raise ValueError('Invalid entity kind')
    if entity.record_type != 'candidate':
        raise ValueError('Only candidates can be promoted')
    if not reason.strip():
        raise ValueError('Promotion requires reason')
    previous_state_id = entity.state_id
    session.info.setdefault("netvoyager_manual_audit", set()).add(id(entity))
    entity.record_type = 'canonical'
    entity.state_id = new_id()
    event = EntityEvent(entity_kind=kind, entity_id=entity.id, event_type='candidate_promoted', previous_state_id=previous_state_id, new_state_id=entity.state_id, from_type='candidate', to_type='canonical', observation_id=observation_id, actor_type=actor_type, actor_id=actor_id, reason=reason, before={'record_type':'candidate'}, after={'record_type':'canonical'})
    session.add(event)
    session.flush()
    return event


def update_relationship(
    session: Session, *, kind: str, relationship, changes: dict,
    actor_type: str, actor_id: str, reason: str,
):
    """Apply an accepted relation change and append its audit event atomically.

    The caller authorizes the change and owns the transaction.
    Identical updates do not change state_id or create events.
    """
    _actor(actor_type, actor_id)
    if not reason or not reason.strip():
        raise ValueError("Relationship update requires reason")
    if not changes:
        return None
    tracked = {"record_type", "status", "relation_type"}
    if set(changes) - tracked:
        raise ValueError("Unsupported relationship state attribute")
    before = {field: getattr(relationship, field) for field in changes}
    after = {field: value for field, value in changes.items() if before[field] != value}
    if not after:
        return None
    session.info.setdefault("netvoyager_manual_audit", set()).add(id(relationship))
    previous_state_id = relationship.state_id
    for field, value in after.items():
        setattr(relationship, field, value)
    relationship.state_id = new_id()
    event = EntityEvent(
        entity_kind=kind, entity_id=relationship.id, event_type="relationship_updated",
        previous_state_id=previous_state_id, new_state_id=relationship.state_id,
        actor_type=actor_type, actor_id=actor_id, reason=reason,
        before={field: before[field] for field in after}, after=after,
    )
    session.add(event)
    session.flush()
    return event
