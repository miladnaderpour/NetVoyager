
"""Tests for canonical network-device SQLAlchemy persistence mapping."""

from ipaddress import IPv4Address
from uuid import uuid4

import pytest
from sqlalchemy import select

from netvoyager_core.exceptions import NetVoyagerInvariantError
from netvoyager_network.device.models import NetworkDevice

from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities import NetworkDeviceEntity
from netvoyager_database.entities.base import Base
from netvoyager_database.mappers.devices.network_device import (
    to_domain,
    to_entity,
)
from netvoyager_database.session import create_session_factory


@pytest.fixture
def session_factory():
    """Provide a fresh SQLite in-memory database for each test."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def test_network_device_mapping_preserves_domain_state():
    """Domain conversion must preserve identity, state, and metadata."""
    device = NetworkDevice(
        name="PAN-020-Main",
        serial_number="023201005462",
        management_ip=IPv4Address("10.131.0.10"),
        manufacturer="Palo Alto",
        asset_tag="ASSET-001",
    )
    device.update_metadata(
        "panorama",
        {"tags": ["production", "firewall"]},
    )

    entity = to_entity(device)
    restored = to_domain(entity)

    assert restored.device_id == device.device_id
    assert restored.state_id == device.state_id
    assert restored.serial_number == device.serial_number
    assert restored.management_ip == device.management_ip
    assert restored.asset_tag == device.asset_tag
    assert restored.metadata == device.metadata


def test_network_device_database_round_trip(session_factory):
    """A persisted device must reconstruct with its original identity."""
    device = NetworkDevice(
        name="DE-MAN-FW-001",
        serial_number="ABC123",
        management_ip=IPv4Address("10.131.0.20"),
    )

    with session_factory() as session:
        session.add(to_entity(device))
        session.commit()

    with session_factory() as session:
        entity = session.scalar(
            select(NetworkDeviceEntity).where(
                NetworkDeviceEntity.device_id == device.device_id
            )
        )

        assert entity is not None

        restored = to_domain(entity)

        assert restored.device_id == device.device_id
        assert restored.state_id == device.state_id
        assert restored.management_ip == device.management_ip
        assert entity.created_at is not None
        assert entity.updated_at is not None
        assert entity.revision == 1


def test_network_device_mapping_rejects_invalid_identity():
    """Stored identities must not override deterministic domain IDs."""
    device = NetworkDevice(name="DE-MAN-FW-001")
    entity = to_entity(device)
    entity.device_id = uuid4()

    with pytest.raises(NetVoyagerInvariantError) as error:
        to_domain(entity)

    assert error.value.code == "database.device_identity_mismatch"


def test_network_device_metadata_is_detached():
    """Changing mapped metadata must not mutate the domain object."""
    device = NetworkDevice(name="DE-MAN-FW-001")
    device.update_metadata("source", {"values": [1, 2]})

    entity = to_entity(device)
    entity.integration_metadata["source"]["values"].append(3)

    assert device.get_metadata("source") == {
        "values": [1, 2],
    }
