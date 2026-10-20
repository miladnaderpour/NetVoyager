
"""Integration tests for packaged Alembic database migrations."""

from pathlib import Path

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from netvoyager_database.engine import create_database_engine
from netvoyager_database.migrations.__main__ import (
    create_migration_config,
)
from netvoyager_database.schema import get_schema_metadata


def test_migrations_create_complete_schema(tmp_path: Path) -> None:
    """Upgrade a fresh persistent SQLite database to the latest revision."""
    database_path = tmp_path / "netvoyager.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    config = create_migration_config(database_url)
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_current_head() is not None

    # Alembic, not create_schema(), must create the database structure.
    command.upgrade(config, "head")

    engine = create_database_engine(database_url)

    try:
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names())

        expected_tables = {
            table_name
            for metadata in get_schema_metadata()
            for table_name in metadata.tables
        }

        assert expected_tables.issubset(actual_tables)
        assert "alembic_version" in actual_tables

        with engine.connect() as connection:
            revision = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )

        assert revision == scripts.get_current_head()

        # Repeated upgrades must not recreate or damage existing tables.
        command.upgrade(config, "head")

        # Confirm there are no pending model/schema upgrade operations.
        command.check(config)

    finally:
        engine.dispose()

