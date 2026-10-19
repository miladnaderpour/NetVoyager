
"""Test SQL evidence persistence and transaction behavior."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from netvoyager_database.exceptions import (
    RepositoryConflictError,
    RepositoryNotFoundError,
)
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_intelligence.base import IntelligenceBase
from netvoyager_intelligence.evidence import (
    EvidenceRecord,
)


@pytest.fixture
def session_factory():
    """Create an isolated SQLite database with foreign keys enabled."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, connection_record):
        """Enable SQLite foreign-key enforcement."""
        connection.execute("PRAGMA foreign_keys=ON")

    IntelligenceBase.metadata.create_all(engine)

    yield create_session_factory(engine)

    engine.dispose()


def test_add_and_get_evidence(session_factory):
    """Persist an evidence record through the Unit of Work."""
    record = EvidenceRecord(
        source="excel",
        details={"row": 10},
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(record)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        loaded = uow.evidence.get(record.id)

        assert loaded is not None
        assert loaded.id == record.id
        assert loaded.source == "excel"
        assert loaded.details == {"row": 10}


def test_duplicate_evidence_is_rejected(session_factory):
    """Reject duplicate evidence identities without replacing data."""
    record = EvidenceRecord(source="excel", details={})

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(record)
        uow.commit()

    with pytest.raises(RepositoryConflictError):
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.evidence.add(
                EvidenceRecord(
                    source="panorama",
                    details={},
                    id=record.id,
                )
            )


def test_evidence_link_is_idempotent(session_factory):
    """Repeated identical links do not create duplicate relations."""
    record = EvidenceRecord(source="excel", details={})
    device_id = uuid4()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(record)

        uow.evidence.link(
            record.id,
            "network_device",
            device_id,
        )
        uow.evidence.link(
            record.id,
            "network_device",
            device_id,
        )
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        relations = uow.evidence.relations_for_object(device_id)

        assert len(relations) == 1
        assert relations[0].evidence_id == record.id


def test_conflicting_object_type_is_rejected(session_factory):
    """Reject conflicting object types for one evidence/object pair."""
    record = EvidenceRecord(source="excel", details={})
    object_id = uuid4()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(record)
        uow.evidence.link(record.id, "network_device", object_id)

        with pytest.raises(RepositoryConflictError):
            uow.evidence.link(
                record.id,
                "network_scope",
                object_id,
            )


def test_link_requires_existing_evidence(session_factory):
    """Reject links referencing evidence that does not exist."""
    with NetworkInventoryUnitOfWork(session_factory) as uow:
        with pytest.raises(RepositoryNotFoundError):
            uow.evidence.link(
                uuid4(),
                "network_device",
                uuid4(),
            )


def test_lookup_deduplicates_evidence(session_factory):
    """Return an evidence record once when linked to several objects."""
    record = EvidenceRecord(source="panorama", details={})
    first_id = uuid4()
    second_id = uuid4()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(record)
        uow.evidence.link(record.id, "network_device", first_id)
        uow.evidence.link(record.id, "network_scope", second_id)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        records = uow.evidence.for_objects((first_id, second_id))

        assert len(records) == 1
        assert records[0].id == record.id


def test_uncommitted_evidence_is_rolled_back(session_factory):
    """Discard evidence and relations when the transaction is not committed."""
    record = EvidenceRecord(source="excel", details={})
    object_id = uuid4()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(record)
        uow.evidence.link(record.id, "network_device", object_id)

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.evidence.get(record.id) is None
        assert uow.evidence.for_object(object_id) == ()
