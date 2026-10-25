"""Run from the unpacked package after installation; uses memory-only SQLite."""
from sqlalchemy import select
from netvoyager_database import Base, Device, Source, EntityEvent, EntityLink, UnitOfWork, create_engine_and_session_factory
from netvoyager_database.lifecycle import record_creation, link_observation, promote_candidate

engine, factory = create_engine_and_session_factory('sqlite:///:memory:')
Base.metadata.create_all(engine)  # Demo only; production uses Alembic
with UnitOfWork(factory) as uow:
    s=uow.session
    source=Source(name='example_excel',source_type='excel')
    s.add(source);s.flush()
    observed=Device(record_type='observation',source_id=source.id,serial_number='00123456',name='LAB-SW1')
    record_creation(s,kind='device',entity=observed,actor_type='system',actor_id='demo-import',source_id=source.id)
    candidate=Device(record_type='candidate',serial_number='00123456',name='LAB-SW1')
    record_creation(s,kind='device',entity=candidate,actor_type='system',actor_id='demo-analysis',observation_id=observed.id)
    link_observation(s,kind='device',observation_id=observed.id,entity_id=candidate.id,actor_type='system',actor_id='demo-analysis')
    original_id=candidate.id
    promote_candidate(s,kind='device',entity=candidate,actor_type='human',actor_id='demo-engineer',reason='Demo approval',observation_id=observed.id)
    uow.commit()
with factory() as s:
    assert s.get(Device,original_id).record_type == 'canonical'
    assert len(s.scalars(select(EntityEvent)).all()) == 4
    assert len(s.scalars(select(EntityLink)).all()) == 1
    print('OK: candidate ID stable, original observation retained, 4 audit events, 1 provenance link')
