
"""Alembic environment for NetVoyager database migrations."""

from __future__ import annotations

from alembic import context
from sqlalchemy.engine import Connection

from netvoyager_database.engine import create_database_engine
from netvoyager_database.schema import get_schema_metadata


config = context.config

# Database and Intelligence retain separate declarative bases.
target_metadata = list(get_schema_metadata())


def _database_url() -> str:
    """Return the database URL supplied to the migration command."""
    url = config.attributes.get("database_url")

    if not isinstance(url, str) or not url.strip():
        raise ValueError(
            "A database URL is required for NetVoyager migrations."
        )

    return url


def _configure_migrations(connection: Connection) -> None:
    """Configure Alembic with the registered database metadata."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )


def run_migrations_offline() -> None:
    """Generate migration SQL without opening a database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Execute migrations using NetVoyager's configured database engine."""
    existing_connection = config.attributes.get("connection")

    if isinstance(existing_connection, Connection):
        _configure_migrations(existing_connection)

        with context.begin_transaction():
            context.run_migrations()

        return

    engine = create_database_engine(_database_url())

    try:
        with engine.connect() as connection:
            _configure_migrations(connection)

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
