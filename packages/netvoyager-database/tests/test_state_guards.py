"""Synthetic tests for ORM observation immutability and state revision."""
import pytest
from sqlalchemy import select
from netvoyager_database import Base, Device, EntityEvent, UnitOfWork, create_engine_and_session_factory
from netvoyager_database.state_guards import InventoryStateError

@pytest.fixture
def factory():
    engine, factory = create_engine_and_session_factory('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    yield factory
    engine.dispose()

def insert(factory, record_type='candidate'):
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        device = Device(record_type=record_type, serial_number='SYN-0001', model='A')
        uow.session.add(device)
        uow.commit()
        return device.id, device.state_id

def test_observation_update_rejected(factory):
    device_id, _ = insert(factory, 'observation')
    with pytest.raises(InventoryStateError):
        with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
            obj = uow.session.get(Device, device_id)
            obj.model = 'B'
            uow.commit()

def test_observation_delete_rejected(factory):
    device_id, _ = insert(factory, 'observation')
    with pytest.raises(InventoryStateError):
        with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
            uow.session.delete(uow.session.get(Device, device_id))
            uow.commit()

def test_observation_cannot_promote_by_direct_assignment(factory):
    device_id, _ = insert(factory, 'observation')
    with pytest.raises(InventoryStateError):
        with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
            uow.session.get(Device, device_id).record_type = 'candidate'
            uow.commit()

def test_accepted_attribute_change_advances_state(factory):
    device_id, prior = insert(factory)
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        obj = uow.session.get(Device, device_id)
        obj.model = 'B'
        uow.commit()
        assert obj.state_id != prior

def test_identical_attribute_value_does_not_advance_state(factory):
    device_id, prior = insert(factory)
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        obj = uow.session.get(Device, device_id)
        obj.model = 'A'
        uow.commit()
        assert obj.state_id == prior

def test_last_seen_only_does_not_advance_state(factory):
    from datetime import datetime, timezone
    device_id, prior = insert(factory)
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        obj = uow.session.get(Device, device_id)
        obj.last_seen = datetime.now(timezone.utc)
        uow.commit()
        assert obj.state_id == prior

def test_failed_observation_update_keeps_original_value(factory):
    device_id, prior = insert(factory, 'observation')
    with pytest.raises(InventoryStateError):
        with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
            uow.session.get(Device, device_id).model = 'B'
            uow.commit()
    with factory() as session:
        obj = session.get(Device, device_id)
        assert obj.model == 'A'
        assert obj.state_id == prior

def test_existing_event_is_immutable(factory):
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        event = EntityEvent(entity_kind='device', entity_id='synthetic', event_type='test', actor_type='system', actor_id='test')
        uow.session.add(event)
        uow.commit()
        eid = event.id
    with pytest.raises(InventoryStateError):
        with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
            uow.session.get(EntityEvent, eid).reason = 'changed'
            uow.commit()
