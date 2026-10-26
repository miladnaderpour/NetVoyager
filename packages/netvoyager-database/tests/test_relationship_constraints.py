"""Synthetic relational integrity tests for the unified schema."""
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from netvoyager_database import Base, Device, Location, NetworkPrefix, AutonomousSystem, Interface, AddressSpace, create_engine_and_session_factory
from netvoyager_database.models.relationships import DeviceConnection, InterfaceConnection, LocationDevice

@pytest.fixture
def db():
    engine, factory = create_engine_and_session_factory("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine, factory
    engine.dispose()

def test_schema_uses_direct_device_interface_fk_and_interface_links(db):
    engine, _ = db
    tables = set(inspect(engine).get_table_names())
    assert 'device_interfaces' not in tables
    assert 'interface_connections' in tables
    assert {'record_type', 'state_id'} <= {c['name'] for c in inspect(engine).get_columns('interface_connections')}

def test_canonical_serial_is_unique_but_observations_can_repeat(db):
    _, factory = db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add_all([Device(record_type='observation', serial_number='S-001'), Device(record_type='candidate', serial_number='S-001'), Device(record_type='canonical', serial_number='S-001')]); s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(Device(record_type='canonical', serial_number='S-001'))
        with pytest.raises(IntegrityError): s.commit()

def test_stack_members_share_hostname_and_ip(db):
    _, factory = db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add_all([Device(record_type='canonical', device_type='physical', serial_number=x, hostname='STACK', management_ip='192.0.2.3') for x in ('ONE','TWO')]);s.commit()

def test_logical_devices_require_unique_key(db):
    _, factory = db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(Device(record_type='canonical', device_type='logical', logical_key='STACK-A'));s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(Device(record_type='canonical', device_type='logical', logical_key='STACK-A'))
        with pytest.raises(IntegrityError):s.commit()

def test_location_hierarchy_and_canonical_code(db):
    _, factory = db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        parent=Location(record_type='canonical', code='COUNTRY')
        s.add(parent);s.flush()
        s.add(Location(record_type='canonical',code='BUILDING',parent_location_id=parent.id));s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(Location(record_type='canonical', code='COUNTRY'))
        with pytest.raises(IntegrityError):s.commit()

def test_address_space_cidr_unique_and_observations_repeat(db):
    _, factory = db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        a,b=AddressSpace(name='GLOBAL'),AddressSpace(name='VRF-A');s.add_all([a,b]);s.flush()
        s.add_all([NetworkPrefix(record_type='canonical',cidr='192.0.2.0/24',address_space_id=a.id), NetworkPrefix(record_type='canonical',cidr='192.0.2.0/24',address_space_id=b.id), NetworkPrefix(record_type='observation',cidr='192.0.2.0/24',address_space_id=a.id)]);s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(NetworkPrefix(record_type='canonical',cidr='192.0.2.0/24',address_space_id=a.id))
        with pytest.raises(IntegrityError):s.commit()

def test_asn_canonical_unique(db):
    _, factory=db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add_all([AutonomousSystem(record_type='canonical',asn=64512),AutonomousSystem(record_type='observation',asn=64512)]);s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(AutonomousSystem(record_type='canonical',asn=64512))
        with pytest.raises(IntegrityError):s.commit()

def test_interface_name_unique_per_device_only(db):
    _, factory=db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        d1,d2=Device(record_type='canonical',serial_number='A'),Device(record_type='canonical',serial_number='B');s.add_all([d1,d2]);s.flush()
        s.add_all([Interface(record_type='canonical',device_id=d1.id,name='Gi0/1'),Interface(record_type='canonical',device_id=d2.id,name='Gi0/1')]);s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(Interface(record_type='canonical',device_id=d1.id,name='Gi0/1'))
        with pytest.raises(IntegrityError):s.commit()

def test_interface_connection_undirected_duplicate_and_self_rejected(db):
    _, factory=db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        d=Device(record_type='canonical',serial_number='SW');s.add(d);s.flush()
        a,b=Interface(record_type='canonical',device_id=d.id,name='Gi0/1'),Interface(record_type='canonical',device_id=d.id,name='Gi0/2');s.add_all([a,b]);s.flush()
        x,y=sorted((a.id,b.id))
        s.add(InterfaceConnection(record_type='canonical',interface_a_id=x,interface_b_id=y,relation_type='physical'));s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(InterfaceConnection(record_type='canonical',interface_a_id=x,interface_b_id=y,relation_type='physical'))
        with pytest.raises(IntegrityError):s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(InterfaceConnection(record_type='candidate',interface_a_id=y,interface_b_id=x,relation_type='physical'))
        with pytest.raises(IntegrityError):s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(InterfaceConnection(record_type='observation',interface_a_id=x,interface_b_id=x,relation_type='physical'))
        with pytest.raises(IntegrityError):s.commit()

def test_membership_uses_device_connections(db):
    _, factory=db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        logical=Device(record_type='canonical',device_type='logical',logical_key='STACK-01')
        physical=Device(record_type='canonical',serial_number='MEMBER-01');s.add_all([logical,physical]);s.flush()
        a,b=sorted((logical.id,physical.id))
        s.add(DeviceConnection(record_type='canonical',device_a_id=a,device_b_id=b,relation_type='member_of'));s.commit()

def test_canonical_relationship_duplicate_blocked_observations_allowed(db):
    _, factory=db
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        d=Device(record_type='canonical',serial_number='EDGE');l=Location(record_type='canonical',code='LAB');s.add_all([d,l]);s.flush()
        s.add_all([LocationDevice(record_type='canonical',location_id=l.id,device_id=d.id,relation_type='located_at'),LocationDevice(record_type='observation',location_id=l.id,device_id=d.id,relation_type='located_at')]);s.commit()
    with factory() as s:
        s.info["netvoyager_actor"] = {"actor_type": "system", "actor_id": "synthetic-test"}
        s.add(LocationDevice(record_type='canonical',location_id=l.id,device_id=d.id,relation_type='located_at'))
        with pytest.raises(IntegrityError):s.commit()
