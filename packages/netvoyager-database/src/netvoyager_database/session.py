
"""Synchronous SQLAlchemy session factory for NetVoyager repositories."""

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(
    engine: Engine,
) -> sessionmaker[Session]:
    """Create sessions with explicit transaction ownership.

    Sessions do not automatically commit when closed.

    The application-level Unit of Work will own commit,
    rollback, and session lifetime.
    """
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
        autocommit=False,
    )
