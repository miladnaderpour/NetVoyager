"""Synthetic tests for the next unified database checkpoint."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from netvoyager_database import (
    Base, Device, NetworkPrefix, AddressSpace, EntityEvent,
    create_engine_and_session_factory,
)
from netvoyager_database.models.relationships import DeviceConnection
from netvoyager_database.lifecycle import update_relationship

@pytest.fixture
def db():
    engine, factory = create_engine_and_session_factory('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    yield factory
    engine.dispose()

@pytest.mark.parametrize('input_cidr,normalized', [
    ('192.0.2.99/24','192.0.2.0/24'),
    ('2001:db8::12/64','2001:db8::/64'),
    (' 198.51.100.0/24 ','198.51.100.0/24'),
])
def test_cidr_is_normalized(input_cidr, normalized, db):
    with db() as session:
        session.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        space=AddressSpace(name='TEST');session.add(space);session.flush()
        prefix=NetworkPrefix(record_type='canonical', address_space_id=space.id, cidr=input_cidr)
        session.add(prefix);session.commit()
        assert prefix.cidr==normalized

def test_invalid_cidr_is_rejected(db):
    with pytest.raises(ValueError):
        NetworkPrefix(record_type='candidate', cidr='not a cidr')

def test_normalized_canonical_cidr_rejects_duplicate(db):
    with db() as session:
        session.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        space=AddressSpace(name='TEST');session.add(space);session.flush()
        session.add(NetworkPrefix(record_type='canonical',address_space_id=space.id,cidr='192.0.2.17/24'))
        session.commit()
        session.add(NetworkPrefix(record_type='canonical',address_space_id=space.id,cidr='192.0.2.89/24'))
        with pytest.raises(IntegrityError):session.commit()

@pytest.mark.parametrize('left_type,right_type', [('physical','physical'),('logical','logical')])
def test_invalid_member_relationship_rejected(db,left_type,right_type):
    with db() as session:
        session.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        a=Device(record_type='candidate',device_type=left_type)
        b=Device(record_type='candidate',device_type=right_type)
        session.add_all([a,b]);session.flush()
        first,second=sorted((a.id,b.id))
        session.add(DeviceConnection(device_a_id=first,device_b_id=second,record_type='candidate',relation_type='member_of'))
        with pytest.raises(ValueError,match='one logical and one physical'):
            session.flush()

def test_relationship_update_records_state_and_noop_is_idempotent(db):
    with db() as session:
        session.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        logical=Device(record_type='canonical',device_type='logical',logical_key='STACK-X')
        physical=Device(record_type='canonical',device_type='physical',serial_number='S-00001')
        session.add_all([logical,physical]);session.flush()
        a,b=sorted((logical.id,physical.id))
        relation=DeviceConnection(device_a_id=a,device_b_id=b,relation_type='member_of',record_type='candidate')
        session.add(relation);session.flush()
        old_state_id=relation.state_id
        event=update_relationship(session,kind='device_connection',relationship=relation,
            changes={'record_type':'canonical'},actor_type='human',actor_id='tester',reason='Approved')
        assert event.previous_state_id==old_state_id
        assert event.new_state_id==relation.state_id
        assert relation.state_id!=old_state_id
        assert event.before=={'record_type':'candidate'}
        assert event.after=={'record_type':'canonical'}
        no_change=update_relationship(session,kind='device_connection',relationship=relation,
            changes={'record_type':'canonical'},actor_type='human',actor_id='tester',reason='Duplicate')
        assert no_change is None
        session.commit()
    with db() as session:
        session.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        assert len(session.scalars(select(EntityEvent).where(EntityEvent.entity_kind=='device_connection')).all())==2  # creation + state transition
