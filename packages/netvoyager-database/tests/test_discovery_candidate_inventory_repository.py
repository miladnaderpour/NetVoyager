
"""SQL repository tests for device discovery inventory attributes.

The repository persists candidate snapshots supplied by Analysis.
It does not decide field authority or create conflict findings.

All test identifiers and addresses are synthetic.
"""

from dataclasses import replace
from ipaddress import IPv4Address

import pytest

from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities.base import Base
from netvoyager_database.repositories.discovery.sql_device_discovery_repository import (
    SqlDeviceDiscoveryRepository,
)
from netvoyager_database.session import create_session_factory
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


@pytest.fixture
def session_factory():
    """Create an isolated SQLite database for each test."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def make_candidate() -> DeviceDiscoveryCandidate:
    """Build a synthetic provisional network device."""
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


def test_repository_creates_candidate_with_inventory_attributes(
    session_factory,
):
    """Candidate creation must persist all reported inventory fields."""
    candidate = make_candidate()

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        repo.add_candidate(candidate)
        session.commit()

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        restored = repo.get_candidate(candidate.candidate_id)

        assert restored == candidate
        assert restored is not None
        assert restored.site == "LAB-A"
        assert restored.role == "access_switch"
        assert restored.primary_ipv4 == IPv4Address("192.0.2.11")


def test_repository_updates_inventory_attributes(
    session_factory,
):
    """Authorized snapshots must retain identity during SQL updates."""
    original = make_candidate()

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        repo.add_candidate(original)
        session.commit()

    updated = replace(
        original,
        site="LAB-B",
        role="distribution_switch",
        primary_ipv4=IPv4Address("198.51.100.11"),
        manufacturer="Updated Vendor",
        model="Updated Model",
        software_version="2.0",
        asset_tag="TEST-ASSET-002",
    )

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        repo.save_candidate(updated)
        session.commit()

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        restored = repo.get_candidate(original.candidate_id)

        assert restored == updated
        assert restored is not None
        assert restored.candidate_id == original.candidate_id

        assert restored.site == "LAB-B"
        assert restored.role == "distribution_switch"
        assert restored.primary_ipv4 == IPv4Address("198.51.100.11")
        assert restored.manufacturer == "Updated Vendor"
        assert restored.model == "Updated Model"
        assert restored.software_version == "2.0"
        assert restored.asset_tag == "TEST-ASSET-002"


def test_repository_update_rollback(
    session_factory,
):
    """Rollback must preserve the previously committed candidate."""
    original = make_candidate()

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        repo.add_candidate(original)
        session.commit()

    changed = replace(
        original,
        site="LAB-C",
        model="Uncommitted Model",
    )

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        repo.save_candidate(changed)
        session.rollback()

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        restored = repo.get_candidate(original.candidate_id)

        assert restored == original
        assert restored is not None
        assert restored.site == "LAB-A"
        assert restored.model == "Example Switch"


def test_repository_can_fill_missing_inventory_attributes(
    session_factory,
):
    """Previously empty attributes can be saved without changing identity."""
    original = DeviceDiscoveryCandidate(
        name="SW-LAB-02",
        serial_number="TEST-SERIAL-002",
    )

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        repo.add_candidate(original)
        session.commit()

    updated = replace(
        original,
        site="LAB-B",
        role="access_switch",
        manufacturer="Example Vendor",
        model="Example Switch",
    )

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        repo.save_candidate(updated)
        session.commit()

    with session_factory() as session:
        repo = SqlDeviceDiscoveryRepository(session)
        restored = repo.get_candidate(original.candidate_id)

        assert restored == updated
        assert restored is not None
        assert restored.candidate_id == original.candidate_id
        assert restored.status == "candidate"
        assert restored.resolved_device_id is None
