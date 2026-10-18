
"""Tests for SQL-backed canonical network-device repositories."""

from ipaddress import IPv4Address

import pytest

from netvoyager_network.device.models import NetworkDevice
from netvoyager_database.exceptions import (
    RepositoryConflictError,
    RepositoryNotFoundError,
)
from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities import NetworkDeviceEntity
from netvoyager_database.entities.base import Base
from netvoyager_database.repositories.devices.network_device import (
    SqlNetworkDeviceRepository,
)
from netvoyager_database.session import create_session_factory


@pytest.fixture
def session_factory():
    """Create an isolated SQLite in-memory database for each test."""
    engine = create_database_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def test_repository_add_and_get_by_id(session_factory):
    """Retrieve a persisted canonical device by its UUID."""
    device = NetworkDevice(
        name="DE-MAN-FW-001",
        serial_number="ABC123",
    )

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(device)
        session.commit()

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)

        restored = repository.get_by_id(device.device_id)

        assert restored is not None
        assert restored.device_id == device.device_id
        assert restored.name == device.name
        assert restored.serial_number == device.serial_number


def test_repository_find_by_name(session_factory):
    """Canonical names must support exact retrieval."""
    device = NetworkDevice(name="DE-MAN-FW-001")

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(device)

        result = repository.find_by_name(device.name)

        assert result is not None
        assert result.device_id == device.device_id

        session.rollback()


def test_repository_returns_multiple_serial_matches(session_factory):
    """Serial lookups must preserve potentially ambiguous identities."""
    first = NetworkDevice(
        name="DE-MAN-FW-001",
        serial_number="SERIAL-001",
    )
    second = NetworkDevice(
        name="DE-MAN-FW-002",
        serial_number="SERIAL-001",
    )

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(first)
        repository.add(second)

        results = repository.find_by_serial("SERIAL-001")

        assert len(results) == 2
        assert {device.device_id for device in results} == {
            first.device_id,
            second.device_id,
        }

        session.rollback()


def test_repository_find_by_management_ip_and_asset_tag(session_factory):
    """Management IP and asset tag support independent exact lookups."""
    device = NetworkDevice(
        name="DE-MAN-FW-001",
        management_ip=IPv4Address("10.131.0.10"),
        asset_tag="ASSET-001",
    )

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(device)

        by_ip = repository.find_by_management_ip(
            IPv4Address("10.131.0.10")
        )
        by_asset = repository.find_by_asset_tag("ASSET-001")

        assert len(by_ip) == 1
        assert len(by_asset) == 1
        assert by_ip[0].device_id == device.device_id
        assert by_asset[0].device_id == device.device_id

        session.rollback()


def test_repository_rejects_duplicate_canonical_identity(session_factory):
    """An existing canonical identity must not be inserted twice."""
    device = NetworkDevice(name="DE-MAN-FW-001")

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(device)
        session.commit()

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)

        with pytest.raises(RepositoryConflictError) as error:
            repository.add(device)

        assert error.value.code == "storage.device_already_exists"

        session.rollback()


def test_repository_save_updates_existing_device(session_factory):
    """Save must persist technical changes without changing identity."""
    device = NetworkDevice(
        name="DE-MAN-FW-001",
        serial_number="SERIAL-OLD",
    )

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(device)
        session.commit()

    original_id = device.device_id
    original_state = device.state_id

    device.serial_number = "SERIAL-NEW"
    device.update_metadata("inventory", {"verified": True})

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.save(device)
        session.commit()

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        restored = repository.get_by_id(original_id)

        assert restored is not None
        assert restored.device_id == original_id
        assert restored.serial_number == "SERIAL-NEW"
        assert restored.state_id != original_state
        assert restored.get_metadata("inventory") == {
            "verified": True,
        }

        entity = session.get(NetworkDeviceEntity, original_id)

        assert entity is not None
        assert entity.revision == 2


def test_repository_save_rejects_missing_device(session_factory):
    """Save must not silently insert a nonexistent canonical device."""
    device = NetworkDevice(name="DE-MAN-FW-999")

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)

        with pytest.raises(RepositoryNotFoundError) as error:
            repository.save(device)

        assert error.value.code == "storage.device_not_found"


def test_repository_rollback_discards_insert(session_factory):
    """Uncommitted repository changes must be reversible."""
    device = NetworkDevice(name="DE-MAN-FW-001")

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(device)

        assert repository.get_by_id(device.device_id) is not None

        session.rollback()

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)

        assert repository.get_by_id(device.device_id) is None


def test_repository_rollback_discards_update(session_factory):
    """Rollback must restore previously committed technical state."""
    device = NetworkDevice(
        name="DE-MAN-FW-001",
        serial_number="SERIAL-OLD",
    )

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.add(device)
        session.commit()

    device.serial_number = "SERIAL-NEW"

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        repository.save(device)

        assert repository.get_by_id(device.device_id).serial_number == (
            "SERIAL-NEW"
        )

        session.rollback()

    with session_factory() as session:
        repository = SqlNetworkDeviceRepository(session)
        restored = repository.get_by_id(device.device_id)

        assert restored is not None
        assert restored.serial_number == "SERIAL-OLD"
