
"""Integration tests for network inventory Unit of Work transactions."""

from __future__ import annotations

import pytest

from netvoyager_network.device.models import NetworkDevice
from netvoyager_database.exceptions import TransactionError

from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities import NetworkDeviceEntity
from netvoyager_database.entities.base import Base
from netvoyager_database.repositories.devices.network_device import (
    SqlNetworkDeviceRepository,
)
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work import (
    BaseUnitOfWork,
    NetworkInventoryUnitOfWork,
)


@pytest.fixture
def session_factory():
    """Provide an isolated SQLite in-memory database per test."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def test_base_unit_of_work_opens_and_closes_session(session_factory):
    """The base class provides a managed database session."""
    with BaseUnitOfWork(session_factory) as uow:
        session = uow.session

        assert session.is_active
        assert session is uow.session

    with pytest.raises(TransactionError) as error:
        _ = uow.session

    assert error.value.code == "storage.unit_of_work_inactive"


def test_inventory_unit_of_work_initializes_repository(session_factory):
    """The inventory repository uses the Unit of Work session."""
    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert isinstance(
            uow.devices,
            SqlNetworkDeviceRepository,
        )


def test_unit_of_work_commits_device(session_factory):
    """Explicit commit persists repository changes."""
    device = NetworkDevice(name="DE-MAN-FW-001")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(device)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        restored = uow.devices.get_by_id(device.device_id)

        assert restored is not None
        assert restored.device_id == device.device_id


def test_unit_of_work_rolls_back_without_commit(session_factory):
    """Leaving the context without commit discards changes."""
    device = NetworkDevice(name="DE-MAN-FW-001")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(device)

        assert uow.devices.get_by_id(device.device_id) is not None

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.devices.get_by_id(device.device_id) is None


def test_unit_of_work_rolls_back_on_exception(session_factory):
    """An exception discards uncommitted repository changes."""
    device = NetworkDevice(name="DE-MAN-FW-001")

    with pytest.raises(ValueError, match="Simulated failure"):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.devices.add(device)
            raise ValueError("Simulated failure")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.devices.get_by_id(device.device_id) is None


def test_unit_of_work_explicit_rollback(session_factory):
    """Explicit rollback discards the current transaction."""
    device = NetworkDevice(name="DE-MAN-FW-001")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(device)
        uow.rollback()

        assert uow.devices.get_by_id(device.device_id) is None


def test_unit_of_work_commits_multiple_devices(session_factory):
    """Multiple device writes participate in the same transaction."""
    first = NetworkDevice(name="DE-MAN-FW-001")
    second = NetworkDevice(name="DE-MAN-FW-002")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(first)
        uow.devices.add(second)

        assert uow.devices.find_by_name(first.name) is not None
        assert uow.devices.find_by_name(second.name) is not None

        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.devices.get_by_id(first.device_id) is not None
        assert uow.devices.get_by_id(second.device_id) is not None


def test_unit_of_work_rejects_reuse(session_factory):
    """A Unit of Work cannot be reused after closing."""
    uow = NetworkInventoryUnitOfWork(session_factory)

    with uow:
        pass

    with pytest.raises(TransactionError) as error:
        with uow:
            pass

    assert error.value.code == "storage.unit_of_work_reuse"


def test_unit_of_work_rejects_inactive_operations(session_factory):
    """Repositories and transaction methods require an active context."""
    uow = NetworkInventoryUnitOfWork(session_factory)

    with pytest.raises(TransactionError):
        _ = uow.devices

    with pytest.raises(TransactionError):
        uow.commit()

    with pytest.raises(TransactionError):
        uow.rollback()


def test_unit_of_work_preserves_committed_transactions(session_factory):
    """A later rollback must not undo an earlier committed transaction."""
    first = NetworkDevice(name="DE-MAN-FW-001")
    second = NetworkDevice(name="DE-MAN-FW-002")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(first)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(second)
        uow.rollback()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.devices.get_by_id(first.device_id) is not None
        assert uow.devices.get_by_id(second.device_id) is None


def test_unit_of_work_rolls_back_multiple_writes(session_factory):
    """All uncommitted writes must be discarded together."""
    first = NetworkDevice(name="DE-MAN-FW-001")
    second = NetworkDevice(name="DE-MAN-FW-002")

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.devices.add(first)
        uow.devices.add(second)

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.devices.get_by_id(first.device_id) is None
        assert uow.devices.get_by_id(second.device_id) is None


def test_unit_of_work_rejects_operations_after_exit(session_factory):
    """A closed Unit of Work must not expose an active repository."""
    uow = NetworkInventoryUnitOfWork(session_factory)

    with uow:
        repository = uow.devices

    with pytest.raises(TransactionError) as error:
        _ = uow.devices

    assert error.value.code == "storage.unit_of_work_inactive"

    # The previously obtained reference does not own a new session.
    assert isinstance(repository, SqlNetworkDeviceRepository)
