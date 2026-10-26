"""Synthetic automatic audit checks; zero production inventory data."""
import pytest
from sqlalchemy import select
from netvoyager_database import Base, Device, EntityEvent, UnitOfWork, create_engine_and_session_factory
from netvoyager_database.state_guards import InventoryStateError

@pytest.fixture
def factory():
    engine, make = create_engine_and_session_factory('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    yield make
    engine.dispose()

def _events(make, id):
    with make() as session:
        return session.scalars(select(EntityEvent).where(EntityEvent.entity_id == id).order_by(EntityEvent.created_at)).all()

def test_automatic_creation_and_accepted_update(factory):
    with UnitOfWork(factory, actor_type='system', actor_id='test-job', reason='Synthetic discovery') as uow:
        d = Device(record_type='candidate', serial_number='TEST-123', model='Model-A')
        uow.session.add(d)
        uow.commit()
        id, first_state = d.id, d.state_id
    with UnitOfWork(factory, actor_type='human', actor_id='synthetic-approver', reason='Corrected model') as uow:
        d = uow.session.get(Device, id)
        d.model = 'Model-B'
        uow.commit()
        second_state = d.state_id
    assert first_state != second_state
    created, updated = _events(factory, id)
    assert created.event_type == 'candidate_created'
    assert created.new_state_id == first_state
    assert updated.event_type == 'attributes_updated'
    assert updated.previous_state_id == first_state
    assert updated.new_state_id == second_state
    assert updated.before == {'model': 'Model-A'}
    assert updated.after == {'model': 'Model-B'}
    assert updated.actor_id == 'synthetic-approver'

def test_noop_does_not_add_event(factory):
    with UnitOfWork(factory, actor_type='system', actor_id='test-job') as uow:
        d = Device(record_type='candidate', serial_number='TEST-456', model='A')
        uow.session.add(d);uow.commit();id,state=d.id,d.state_id
    with UnitOfWork(factory, actor_type='system', actor_id='test-job') as uow:
        d = uow.session.get(Device, id)
        d.model = 'A'
        uow.commit()
        assert d.state_id == state
    assert len(_events(factory, id)) == 1

def test_missing_actor_rejects_automatic_update(factory):
    with UnitOfWork(factory, actor_type='system', actor_id='test-job') as uow:
        d = Device(record_type='candidate', serial_number='TEST-789', model='A')
        uow.session.add(d);uow.commit();id=d.id
    with pytest.raises(InventoryStateError, match='actor context'):
        with UnitOfWork(factory) as uow:
            uow.session.get(Device,id).model = 'B'
            uow.commit()
    with factory() as session:
        assert session.get(Device,id).model == 'A'
    assert len(_events(factory, id)) == 1

def test_update_and_event_roll_back_together(factory):
    with UnitOfWork(factory, actor_type='system', actor_id='test-job') as uow:
        d = Device(record_type='candidate',serial_number='TEST-XYZ',model='A')
        uow.session.add(d);uow.commit();id,state=d.id,d.state_id
    with UnitOfWork(factory, actor_type='human', actor_id='tester', reason='Test rollback') as uow:
        uow.session.get(Device,id).model='B'
        uow.session.flush()
        # Intentionally no commit
    with factory() as session:
        d=session.get(Device,id)
        assert d.model=='A'
        assert d.state_id==state
    assert len(_events(factory,id))==1

def test_direct_candidate_promotion_generates_one_event(factory):
    with UnitOfWork(factory, actor_type='system', actor_id='test-job') as uow:
        d=Device(record_type='candidate',serial_number='TEST-PRO')
        uow.session.add(d);uow.commit();id,old=d.id,d.state_id
    with UnitOfWork(factory, actor_type='human', actor_id='tester',reason='Approved') as uow:
        d=uow.session.get(Device,id)
        d.record_type='canonical'
        uow.commit()
        assert d.state_id != old
    ev=_events(factory,id)
    assert len(ev)==2
    assert ev[1].event_type=='candidate_promoted'
    assert ev[1].before == {'record_type':'candidate'}
