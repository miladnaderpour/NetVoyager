
"""SQL mapping tests for device discovery candidate inventory attributes.

Verify that reported inventory attributes survive domain-to-entity mapping,
SQLite persistence, and entity-to-domain reconstruction.

All test inventory identifiers and addresses are synthetic.
"""

from ipaddress import IPv4Address

import pytest

from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities.base import Base
from netvoyager_database.entities.devices.discovery_candidate import (
    DeviceDiscoveryCandidateEntity,
)
from netvoyager_database.mappers.devices.discovery_candidate import (
    candidate_to_domain,
    candidate_to_entity,
)
from netvoyager_database.session import create_session_factory
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


@pytest.fixture
def session_factory():
    """Provide isolated in-memory SQLite persistence for each test."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        yield create_session_factory(engine)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def make_candidate() -> DeviceDiscoveryCandidate:
    """Create a synthetic candidate with all inventory attributes."""
    return DeviceDiscoveryCandidate(
        name="SW-LAB-01",
        host_name="sw-lab-01.example.invalid",
        serial_number="TEST-SERIAL-001",
        management_ip=IPv4Address("192.0.2.10"),
        site="LAB-A",
        role="access_switch",
        primary_ipv4=IPv4Address("192.0.2.11"),
        manufacturer="Example Vendor",
        model="Example Switch",
        software_version="1.0",
        asset_tag="TEST-ASSET-001",
    )


def test_inventory_mapper_preserves_all_attributes():
    """Mapping must preserve candidate identity and reported attributes."""
    candidate = make_candidate()

    entity = candidate_to_entity(candidate)

    assert entity.candidate_id == candidate.candidate_id
    assert entity.status == candidate.status

    assert entity.name == "SW-LAB-01"
    assert entity.host_name == "sw-lab-01.example.invalid"
    assert entity.serial_number == "TEST-SERIAL-001"
    assert entity.management_ip == "192.0.2.10"

    assert entity.site == "LAB-A"
    assert entity.role == "access_switch"
    assert entity.primary_ipv4 == "192.0.2.11"
    assert entity.manufacturer == "Example Vendor"
    assert entity.model == "Example Switch"
    assert entity.software_version == "1.0"
    assert entity.asset_tag == "TEST-ASSET-001"

    restored = candidate_to_domain(entity)

    assert restored == candidate


def test_inventory_attributes_survive_sqlite_round_trip(
    session_factory,
):
    """SQLite must preserve all attributes and the original candidate UUID."""
    candidate = make_candidate()

    with session_factory() as session:
        session.add(candidate_to_entity(candidate))
        session.commit()

    with session_factory() as session:
        entity = session.get(
            DeviceDiscoveryCandidateEntity,
            candidate.candidate_id,
        )

        assert entity is not None

        restored = candidate_to_domain(entity)

        assert restored == candidate
        assert restored.candidate_id == candidate.candidate_id

        assert restored.site == "LAB-A"
        assert restored.role == "access_switch"
        assert restored.primary_ipv4 == IPv4Address("192.0.2.11")
        assert restored.manufacturer == "Example Vendor"
        assert restored.model == "Example Switch"
        assert restored.software_version == "1.0"
        assert restored.asset_tag == "TEST-ASSET-001"


def test_candidate_without_inventory_attributes(
    session_factory,
):
    """Minimal candidates must remain valid after extending the schema."""
    candidate = DeviceDiscoveryCandidate(
        name="FW-LAB-01",
        serial_number="TEST-SERIAL-002",
    )

    with session_factory() as session:
        session.add(candidate_to_entity(candidate))
        session.commit()

    with session_factory() as session:
        entity = session.get(
            DeviceDiscoveryCandidateEntity,
            candidate.candidate_id,
        )

        assert entity is not None

        restored = candidate_to_domain(entity)

        assert restored == candidate

        assert restored.site is None
        assert restored.role is None
        assert restored.primary_ipv4 is None
        assert restored.manufacturer is None
        assert restored.model is None
        assert restored.software_version is None
        assert restored.asset_tag is None

        assert restored.status == "candidate"
        assert restored.resolved_device_id is None
