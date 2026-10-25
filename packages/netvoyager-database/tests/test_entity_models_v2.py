"""Synthetic checks for unified identity models and lifecycle state."""
from sqlalchemy import inspect, select
from netvoyager_database import (Base, Device, Location, NetworkPrefix, AutonomousSystem,
    Interface, AddressSpace, EntityEvent, UnitOfWork, create_engine_and_session_factory)
from netvoyager_database.lifecycle import record_creation, promote_candidate

def test_schema_contains_new_attributes():
    engine, _ = create_engine_and_session_factory("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert {"device_type", "logical_key", "state_id"} <= {col["name"] for col in inspector.get_columns("devices")}
    assert {"vrf", "vlan", "status", "state_id"} <= {col["name"] for col in inspector.get_columns("network_prefixes")}
    assert {"previous_state_id", "new_state_id"} <= {col["name"] for col in inspector.get_columns("entity_events")}
    engine.dispose()

def test_stack_physical_and_logical_devices_share_host_and_ip():
    engine, factory = create_engine_and_session_factory("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with UnitOfWork(factory) as uow:
        logical = Device(record_type="canonical", device_type="logical", logical_key="STACK-LAB", hostname="STACK-LAB", management_ip="192.0.2.4")
        member1 = Device(record_type="canonical", device_type="physical", serial_number="SERIAL-A", hostname="STACK-LAB", management_ip="192.0.2.4")
        member2 = Device(record_type="canonical", device_type="physical", serial_number="SERIAL-B", hostname="STACK-LAB", management_ip="192.0.2.4")
        uow.session.add_all((logical, member1, member2))
        uow.commit()
    with factory() as session:
        assert len(session.scalars(select(Device)).all()) == 3
    engine.dispose()

def test_promotion_preserves_identity_and_versions_state():
    engine, factory = create_engine_and_session_factory("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with UnitOfWork(factory) as uow:
        candidate = Device(record_type="candidate", serial_number="LAB-0001")
        record_creation(uow.session, kind="device", entity=candidate, actor_type="system", actor_id="tester")
        old_id, old_state_id = candidate.id, candidate.state_id
        promote_candidate(uow.session, kind="device", entity=candidate, actor_type="human", actor_id="approver", reason="Approved")
        assert candidate.id == old_id
        assert candidate.state_id != old_state_id
        uow.commit()
    with factory() as session:
        event = session.scalars(select(EntityEvent).where(EntityEvent.event_type == "candidate_promoted")).one()
        assert event.previous_state_id == old_state_id
        assert event.new_state_id == session.get(Device, old_id).state_id
    engine.dispose()
