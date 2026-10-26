"""Fully synthetic database tests."""
import pytest
from sqlalchemy import select, inspect
from netvoyager_database import Base, Device, Source, EntityEvent, EntityLink, Location, NetworkPrefix, AutonomousSystem, Interface, UnitOfWork, create_engine_and_session_factory
from netvoyager_database.lifecycle import record_creation, link_observation, promote_candidate

@pytest.fixture
def environment():
    engine,factory=create_engine_and_session_factory('sqlite:///:memory:')
    Base.metadata.create_all(engine)  # isolated tests only
    yield engine,factory
    engine.dispose()

def test_five_primary_tables(environment):
    engine,_=environment
    names=set(inspect(engine).get_table_names())
    assert {'locations','network_prefixes','devices','autonomous_systems','interfaces'}.issubset(names)
    assert {'entity_events','entity_links','findings','evidence','prefix_as'}.issubset(names)

def test_observation_candidate_promotion_history(environment):
    _,factory=environment
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        source=Source(name='test_excel',source_type='excel')
        uow.session.add(source);uow.session.flush()
        observation=Device(record_type='observation',serial_number='000123456',source_id=source.id)
        record_creation(uow.session,kind='device',entity=observation,actor_type='system',actor_id='test-import',source_id=source.id)
        candidate=Device(record_type='candidate',serial_number='000123456')
        record_creation(uow.session,kind='device',entity=candidate,actor_type='system',actor_id='test-analysis',observation_id=observation.id)
        link_observation(uow.session,kind='device',observation_id=observation.id,entity_id=candidate.id,actor_type='system',actor_id='test-analysis')
        old_id=candidate.id
        promote_candidate(uow.session,kind='device',entity=candidate,actor_type='human',actor_id='test-engineer',reason='Approved',observation_id=observation.id)
        uow.commit()
    with factory() as s:
        assert s.get(Device,old_id).record_type=='canonical'
        assert s.get(Device,observation.id).record_type=='observation'
        assert len(s.scalars(select(EntityEvent)).all())==4
        assert len(s.scalars(select(EntityLink)).all())==1

def test_rollback_is_atomic(environment):
    _,factory=environment
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        record_creation(uow.session,kind='device',entity=Device(record_type='candidate',serial_number='TEST-1'),actor_type='system',actor_id='test')
        # no commit
    with factory() as s:
        assert s.scalars(select(Device)).all()==[]
        assert s.scalars(select(EntityEvent)).all()==[]

def test_cannot_promote_observation(environment):
    _,factory=environment
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        obs=Device(record_type='observation',serial_number='TEST-1')
        record_creation(uow.session,kind='device',entity=obs,actor_type='system',actor_id='test')
        with pytest.raises(ValueError,match='Only candidates'):
            promote_candidate(uow.session,kind='device',entity=obs,actor_type='human',actor_id='tester',reason='Test')

def test_authorized_actor_is_required(environment):
    _,factory=environment
    with UnitOfWork(factory, actor_type="system", actor_id="synthetic-test") as uow:
        with pytest.raises(ValueError,match='identified'):
            record_creation(uow.session,kind='device',entity=Device(record_type='candidate',serial_number='TEST-1'),actor_type='system',actor_id='')
