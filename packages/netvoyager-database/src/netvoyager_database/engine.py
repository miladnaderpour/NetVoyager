
"""SQLAlchemy engine creation for NetVoyager database backends.

Engine configuration is independent of domain models and repositories.
The caller owns engine lifetime and resource disposal.
"""

from __future__ import annotations

import sqlite3

from sqlalchemy.engine import Connection
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.pool import StaticPool

from netvoyager_core.logging import get_logger

from .exceptions import DatabaseConfigurationError


logger = get_logger(__name__)


def create_database_engine(
    url: str,
    *,
    echo: bool = False,
) -> Engine:
    """Create a synchronous SQLAlchemy engine.

    SQLite in-memory databases use a single connection suitable for
    sequential integration tests. SQLite transaction control is
    configured explicitly for compatible Python versions.

    The engine does not create schemas or open a transaction.
    """
    try:
        database_url = make_url(url)
    except (ArgumentError, ValueError) as exc:
        raise DatabaseConfigurationError(
            code="database.invalid_url",
            message="Invalid database connection URL.",
        ) from exc

    backend = database_url.get_backend_name()

    try:
        if backend == "sqlite":
            is_memory = (
                database_url.database in (None, "", ":memory:")
                and not database_url.query
            )

            options: dict[str, object] = {}

            if is_memory:
                options["poolclass"] = StaticPool
                options["connect_args"] = {
                    "check_same_thread": False,
                }

            engine = create_engine(
                database_url,
                echo=echo,
                **options,
            )

            _configure_sqlite(engine)
        else:
            engine = create_engine(
                database_url,
                echo=echo,
            )

    except (SQLAlchemyError, TypeError, ValueError) as exc:
        raise DatabaseConfigurationError(
            code="database.engine_creation_failed",
            message="Unable to create the database engine.",
            details={"backend": backend},
        ) from exc

    logger.debug(
        "Database engine created",
        extra={
            "backend": backend,
            "in_memory": backend == "sqlite"
            and database_url.database in (None, "", ":memory:")
            and not database_url.query,
        },
    )

    return engine



def _configure_sqlite(engine: Engine) -> None:
    """Enable foreign keys and explicit SQLite transaction control."""

    @event.listens_for(engine, "connect")
    def on_connect(
        dbapi_connection: sqlite3.Connection,
        connection_record: object,
    ) -> None:
        """Configure a newly created SQLite DB-API connection."""
        dbapi_connection.isolation_level = None

        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def on_begin(connection: Connection) -> None:
        """Explicitly begin a SQLite transaction."""
        connection.exec_driver_sql("BEGIN")
