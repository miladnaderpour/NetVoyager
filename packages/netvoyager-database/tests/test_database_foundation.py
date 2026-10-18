
"""Tests for SQLAlchemy engine, sessions, and transaction behavior."""

import pytest

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError

from netvoyager_core.exceptions import NetVoyagerError
from netvoyager_database.entities.base import Base
from netvoyager_database.engine import create_database_engine
from netvoyager_database.exceptions import DatabaseConfigurationError
from netvoyager_database.session import create_session_factory


@pytest.fixture
def database():
    """Provide an isolated SQLite in-memory database for each test."""
    engine = create_database_engine("sqlite:///:memory:")

    metadata = MetaData()

    devices = Table(
        "test_devices",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False, unique=True),
    )

    children = Table(
        "test_children",
        metadata,
        Column("id", Integer, primary_key=True),
        Column(
            "device_id",
            Integer,
            ForeignKey("test_devices.id"),
            nullable=False,
        ),
    )

    metadata.create_all(engine)

    try:
        yield engine, create_session_factory(engine), devices, children
    finally:
        engine.dispose()


def test_database_metadata_naming_conventions():
    """The shared base must provide deterministic constraint names."""
    convention = Base.metadata.naming_convention

    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert convention["fk"].startswith("fk_")


def test_database_commit(database):
    """Committed data must remain available to another session."""
    _, session_factory, devices, _ = database

    with session_factory() as session:
        session.execute(devices.insert().values(id=1, name="FW-001"))
        session.commit()

    with session_factory() as session:
        names = session.execute(
            select(devices.c.name)
        ).scalars().all()

    assert names == ["FW-001"]


def test_database_explicit_rollback(database):
    """A rollback must discard uncommitted inserts."""
    _, session_factory, devices, _ = database

    with session_factory() as session:
        session.execute(devices.insert().values(id=1, name="FW-001"))
        session.rollback()

    with session_factory() as session:
        count = session.scalar(
            select(func.count()).select_from(devices)
        )

    assert count == 0


def test_database_rollback_on_exception(database):
    """Closing a failed session must not commit pending changes."""
    _, session_factory, devices, _ = database

    with pytest.raises(RuntimeError):
        with session_factory() as session:
            session.execute(
                devices.insert().values(id=1, name="FW-001")
            )
            raise RuntimeError("Simulated failure")

    with session_factory() as session:
        count = session.scalar(
            select(func.count()).select_from(devices)
        )

    assert count == 0


def test_database_unique_constraint(database):
    """Duplicate device names must be rejected by the database."""
    _, session_factory, devices, _ = database

    with session_factory() as session:
        session.execute(
            devices.insert().values(id=1, name="FW-001")
        )
        session.commit()

    with session_factory() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                devices.insert().values(id=2, name="FW-001")
            )
        session.rollback()


def test_database_foreign_key_constraint(database):
    """SQLite must enforce foreign-key constraints."""
    _, session_factory, _, children = database

    with session_factory() as session:
        with pytest.raises(IntegrityError):
            session.execute(
                children.insert().values(
                    id=1,
                    device_id=999,
                )
            )
        session.rollback()


def test_invalid_database_url():
    """Invalid connection URLs must use NetVoyager exceptions."""
    with pytest.raises(DatabaseConfigurationError) as error:
        create_database_engine("not-a-database-url")

    assert isinstance(error.value, NetVoyagerError)
    assert error.value.code == "database.invalid_url"
