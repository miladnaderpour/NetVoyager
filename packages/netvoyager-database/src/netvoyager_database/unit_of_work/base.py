
"""Shared SQLAlchemy Unit of Work transaction lifecycle.

A Unit of Work owns a single SQLAlchemy session.

Transactions require explicit commit. Uncommitted changes are rolled
back when the context exits, and the session is always closed.
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from netvoyager_core.logging import get_logger
from netvoyager_database.exceptions import TransactionError


logger = get_logger(__name__)


class BaseUnitOfWork:
    """Provide transaction management for database Unit of Work classes.

    Instances are single-use. Subclasses may initialize repositories
    through _initialize_repositories() after the session is created.

    Repositories must not independently commit or roll back.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
    ) -> None:
        """Initialize the Unit of Work without opening a session."""
        self._session_factory = session_factory
        self._session: Session | None = None
        self._entered = False
        self._closed = False

    @property
    def session(self) -> Session:
        """Return the active SQLAlchemy session."""
        return self._require_active()

    def __enter__(self) -> Self:
        """Open a session and initialize transaction-scoped resources."""
        if self._entered or self._closed:
            raise TransactionError(
                code="storage.unit_of_work_reuse",
                message="A Unit of Work cannot be entered more than once.",
            )

        session = self._session_factory()
        self._session = session
        self._entered = True

        try:
            self._initialize_repositories()
        except Exception:
            try:
                session.rollback()
            finally:
                session.close()
                self._session = None
                self._closed = True
            raise

        logger.debug("Database Unit of Work opened")

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Roll back pending work and close the database session."""
        session = self._session

        try:
            if session is not None:
                session.rollback()
        finally:
            try:
                if session is not None:
                    session.close()
            finally:
                self._session = None
                self._closed = True

        logger.debug(
            "Database Unit of Work closed",
            extra={
                "exception": (
                    exc_type.__name__
                    if exc_type is not None
                    else None
                ),
            },
        )

        return False

    def commit(self) -> None:
        """Commit all changes in the current transaction."""
        session = self._require_active()

        try:
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Database Unit of Work commit failed")
            raise

        logger.debug("Database Unit of Work committed")

    def rollback(self) -> None:
        """Discard changes in the current transaction."""
        session = self._require_active()

        session.rollback()

        logger.debug("Database Unit of Work rolled back")

    def _initialize_repositories(self) -> None:
        """Initialize repositories after the session becomes available.

        Subclasses override this method when repositories are required.
        """

    def _require_active(self) -> Session:
        """Return the session or reject an inactive Unit of Work."""
        if (
            not self._entered
            or self._closed
            or self._session is None
        ):
            raise TransactionError(
                code="storage.unit_of_work_inactive",
                message="The Unit of Work is not active.",
            )

        return self._session
