
"""Tests for discovery-candidate entity mapping and SQLite persistence."""

from datetime import UTC, datetime, timedelta, timezone
from ipaddress import IPv4Address

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.models import NetworkDevice

from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities import (
    DeviceDiscoveryCandidateEntity,
)
from netvoyager_database.entities.base import Base
from netvoyager_database.mappers.devices.discovery_candidate import (
    candidate_to_domain,
    candidate_to_entity,
)
from netvoyager_database.mappers.devices.network_device import to_entity
from netvoyager_database.session import create_session_factory


@pytest.fixture
def session_factory():
    """Create a fresh SQLite database with registered entity tables."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def test_candidate_mapping_preserves_identity_and_attributes():
    """Conversion must preserve candidate identity and summary fields."""
    candidate = DeviceDiscoveryCandidate(
        name="PAN-020-Main",
        host_name="pan020",
        serial_number="0012345",
        management_ip=IPv4Address("10.131.0.10"),
    )

    restored = candidate_to_domain(candidate_to_entity(candidate))

    assert restored == candidate
    assert restored.candidate_id == candidate.candidate_id


def test_candidate_database_round_trip(session_factory):
    """SQLite persistence must preserve the candidate snapshot."""
    candidate = DeviceDiscoveryCandidate(
        name="DE-MAN-FW-001",
        serial_number="SERIAL-001",
        management_ip=IPv4Address("10.131.0.20"),
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
        assert entity.created_at is not None
        assert entity.updated_at is not None


def test_candidates_can_share_identity_attributes(session_factory):
    """Duplicate observed identifiers must not collapse candidates."""
    first = DeviceDiscoveryCandidate(
        name="FW",
        serial_number="SERIAL-001",
    )
    second = DeviceDiscoveryCandidate(
        name="FW",
        serial_number="SERIAL-001",
    )

    with session_factory() as session:
        session.add_all((
            candidate_to_entity(first),
            candidate_to_entity(second),
        ))
        session.commit()

    with session_factory() as session:
        entities = session.scalars(
            select(DeviceDiscoveryCandidateEntity).where(
                DeviceDiscoveryCandidateEntity.serial_number
                == "SERIAL-001"
            )
        ).all()

        assert len(entities) == 2
        assert {item.candidate_id for item in entities} == {
            first.candidate_id,
            second.candidate_id,
        }


def test_candidate_timestamps_normalize_to_utc(session_factory):
    """Timezone-aware discovery values remain equivalent after storage."""
    offset = timezone(timedelta(hours=2))
    first_seen = datetime(2026, 10, 17, 12, 0, tzinfo=offset)
    last_seen = datetime(2026, 10, 17, 13, 0, tzinfo=offset)

    candidate = DeviceDiscoveryCandidate(
        first_seen=first_seen,
        last_seen=last_seen,
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

        assert restored.first_seen == first_seen
        assert restored.last_seen == last_seen
        assert restored.first_seen.utcoffset() == timedelta(0)


def test_candidate_resolution_references_existing_device(session_factory):
    """Resolved candidates may reference a persisted canonical device."""
    device = NetworkDevice(name="PAN-020-Main")
    candidate = DeviceDiscoveryCandidate(
        status="resolved",
        resolved_device_id=device.device_id,
    )

    with session_factory() as session:
        session.add(to_entity(device))
        session.flush()

        session.add(candidate_to_entity(candidate))
        session.commit()

    with session_factory() as session:
        entity = session.get(
            DeviceDiscoveryCandidateEntity,
            candidate.candidate_id,
        )

        assert entity is not None
        assert candidate_to_domain(entity) == candidate



def test_candidate_rejects_missing_canonical_reference(session_factory):
    """Foreign keys must prevent resolutions to nonexistent devices."""
    device = NetworkDevice(name="MISSING-DEVICE")
    candidate = DeviceDiscoveryCandidate(
        status="resolved",
        resolved_device_id=device.device_id,
    )

    with session_factory() as session:
        session.add(candidate_to_entity(candidate))

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_candidate_rejects_duplicate_uuid(session_factory):
    """Independent candidates must have unique candidate IDs."""
    candidate = DeviceDiscoveryCandidate(name="FW")

    with session_factory() as session:
        session.add(candidate_to_entity(candidate))
        session.commit()

    with session_factory() as session:
        session.add(candidate_to_entity(candidate))

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
