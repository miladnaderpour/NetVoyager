
"""Shared database fixtures for NetVoyager intelligence tests."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from netvoyager_intelligence.base import IntelligenceBase
from netvoyager_intelligence.evidence import EvidenceRecord, EvidenceRelation
from netvoyager_intelligence.findings import Finding


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Create an isolated SQLite database with foreign keys enabled."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:
        """Enable SQLite foreign-key enforcement."""
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    IntelligenceBase.metadata.create_all(engine)

    yield engine

    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Provide sessions that retain loaded attributes after commit."""
    return sessionmaker(bind=engine, expire_on_commit=False)
