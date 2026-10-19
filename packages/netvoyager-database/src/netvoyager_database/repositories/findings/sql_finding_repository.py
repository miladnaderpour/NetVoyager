
"""SQLAlchemy repository for analysis findings.

Findings are SQLAlchemy-native intelligence models. The repository
persists and retrieves records without performing analysis, validation,
or reconciliation decisions.

All operations use a caller-owned Session. Transaction commit and
rollback belong to the Unit of Work.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from netvoyager_core.logging import get_logger
from netvoyager_database.exceptions import RepositoryConflictError
from netvoyager_intelligence.findings import Finding


logger = get_logger(__name__)


class SqlFindingRepository:
    """Persist and retrieve findings using SQLAlchemy.

    The repository supports direct identity, domain-object, and
    classification lookups without interpreting finding details.

    Write operations flush pending changes but never commit or
    independently roll back the transaction.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the repository with an existing SQLAlchemy session."""
        self._session = session

    def add(self, finding: Finding) -> None:
        """Insert a finding without replacing an existing record.

        A conflicting primary key raises RepositoryConflictError.
        Other persistence errors propagate to the Unit of Work.
        """
        self._session.add(finding)

        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code="storage.finding_conflict",
                message="Cannot insert a conflicting finding record.",
                details={
                    "finding_id": str(finding.id),
                    "kind": finding.kind,
                },
            ) from exc

        logger.debug(
            "Finding inserted",
            extra={
                "finding_id": str(finding.id),
                "kind": finding.kind,
                "severity": finding.severity,
            },
        )

    def get(self, finding_id: UUID) -> Finding | None:
        """Return the finding identified by UUID, if present."""
        return self._session.get(Finding, finding_id)

    def for_object(
        self,
        object_id: UUID,
        *,
        object_type: str | None = None,
    ) -> tuple[Finding, ...]:
        """Return findings associated with one domain-object UUID.

        An optional object type limits results to the expected domain.
        Findings are ordered by creation time and UUID.
        """
        statement = select(Finding).where(
            Finding.object_id == object_id
        )

        if object_type is not None:
            statement = statement.where(
                Finding.object_type == object_type
            )

        statement = statement.order_by(
            Finding.created_at,
            Finding.id,
        )

        return tuple(self._session.scalars(statement).all())

    def find_by_kind(
        self,
        kind: str,
    ) -> tuple[Finding, ...]:
        """Return findings matching the supplied classification."""
        statement = (
            select(Finding)
            .where(Finding.kind == kind)
            .order_by(
                Finding.created_at,
                Finding.id,
            )
        )

        return tuple(self._session.scalars(statement).all())
