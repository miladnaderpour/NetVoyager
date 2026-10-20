
"""Tests for discovery-decision mapping and SQLite persistence."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from netvoyager_network.device.discovery.decisions import (
    DeviceDiscoveryDecision,
)
from netvoyager_database.engine import create_database_engine
from netvoyager_database.entities import DeviceDiscoveryDecisionEntity
from netvoyager_database.mappers.devices.discovery_decision import (
    decision_to_domain,
    decision_to_entity,
)
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory


@pytest.fixture
def session_factory():
    """Provide an isolated database with registered model tables."""
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)

    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def _decision(
    *,
    actor_type="human",
    actor_id="entra:engineer-001",
    subject_type="relationship",
) -> DeviceDiscoveryDecision:
    """Build a representative authorized discovery decision."""
    return DeviceDiscoveryDecision(
        decision_type="relationship_status",
        subject_id=uuid4(),
        previous_value="possible",
        new_value="confirmed",
        evidence_ids=(uuid4(), uuid4()),
        reason="Verified matching physical-device serial number.",
        timestamp=datetime.now(UTC),
        source_id="manual-review",
        method="manual",
        policy_version=1,
        subject_type=subject_type,
        actor_type=actor_type,
        actor_id=actor_id,
    )


def test_decision_mapping_preserves_audit_data() -> None:
    """Round-trip all domain decision fields."""
    decision = _decision()

    restored = decision_to_domain(decision_to_entity(decision))

    assert restored == decision


@pytest.mark.parametrize(
    ("actor_type", "actor_id"),
    [
        ("human", "entra:engineer-001"),
        ("system", "netvoyager-reconciliation"),
        ("ai_agent", "netvoyager-identity-agent"),
    ],
)
def test_decision_supports_actor_types(
    actor_type: str,
    actor_id: str,
) -> None:
    """Preserve human, system, and AI agent attribution."""
    decision = _decision(
        actor_type=actor_type,
        actor_id=actor_id,
    )

    restored = decision_to_domain(decision_to_entity(decision))

    assert restored.actor_type == actor_type
    assert restored.actor_id == actor_id


def test_decision_persists_in_sqlite(session_factory) -> None:
    """Persist and reload an independent audit record."""
    decision = _decision()

    with session_factory() as session:
        entity = decision_to_entity(decision)
        session.add(entity)
        session.flush()
        decision_id = entity.decision_id
        session.commit()

    with session_factory() as session:
        loaded = session.get(DeviceDiscoveryDecisionEntity, decision_id)

        assert loaded is not None
        assert decision_to_domain(loaded) == decision


def test_repeated_decisions_receive_distinct_record_ids(
    session_factory,
) -> None:
    """Never collapse separate decision events with identical content."""
    decision = _decision()

    with session_factory() as session:
        first = decision_to_entity(decision)
        second = decision_to_entity(decision)

        session.add_all([first, second])
        session.flush()

        first_id = first.decision_id
        second_id = second.decision_id
        session.commit()

    assert first_id != second_id

    with session_factory() as session:
        decisions = session.scalars(
            select(DeviceDiscoveryDecisionEntity).where(
                DeviceDiscoveryDecisionEntity.decision_id.in_(
                    (first_id, second_id)
                )
            )
        ).all()

        assert len(decisions) == 2


def test_decision_timestamp_normalizes_to_utc() -> None:
    """Preserve the instant represented by a non-UTC timestamp."""
    decision = _decision()
    local_time = datetime(
        2026, 10, 20, 18, 30,
        tzinfo=timezone_offset(),
    )

    decision = DeviceDiscoveryDecision(
        decision_type=decision.decision_type,
        subject_id=decision.subject_id,
        previous_value=decision.previous_value,
        new_value=decision.new_value,
        evidence_ids=decision.evidence_ids,
        reason=decision.reason,
        timestamp=local_time,
        source_id=decision.source_id,
        method=decision.method,
        policy_version=decision.policy_version,
        subject_type=decision.subject_type,
        actor_type=decision.actor_type,
        actor_id=decision.actor_id,
    )

    restored = decision_to_domain(decision_to_entity(decision))

    assert restored.timestamp == local_time.astimezone(UTC)


def timezone_offset():
    """Provide a fixed UTC+02:00 offset for normalization testing."""
    from datetime import timezone

    return timezone(timedelta(hours=2))


def test_decision_is_immutable() -> None:
    """Prevent accidental mutation of the domain audit record."""
    decision = _decision()

    with pytest.raises(FrozenInstanceError):
        decision.actor_id = "another-engineer"


@pytest.mark.parametrize(
    ("subject_type", "actor_type", "actor_id"),
    [
        ("unknown", "human", "engineer"),
        ("candidate", "unknown", "engineer"),
        ("candidate", "human", ""),
    ],
)
def test_invalid_audit_metadata_is_rejected(
    subject_type: str,
    actor_type: str,
    actor_id: str,
) -> None:
    """Require valid audit subject and actor metadata."""
    with pytest.raises(ValueError):
        _decision(
            subject_type=subject_type,
            actor_type=actor_type,
            actor_id=actor_id,
        )


def test_decision_table_is_registered() -> None:
    """Include discovery decision history in Database metadata."""
    engine = create_database_engine("sqlite:///:memory:")

    try:
        create_schema(engine)
        assert "device_discovery_decisions" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
