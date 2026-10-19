
"""SQLAlchemy repository for evidence records and provenance relations.

Evidence records and relations are SQLAlchemy-native intelligence
models. The repository operates within a caller-owned Session.

Write operations flush pending changes but never commit or roll back.
Transaction ownership belongs to the Unit of Work.
"""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from netvoyager_core.logging import get_logger
from netvoyager_database.exceptions import (
    RepositoryConflictError,
    RepositoryNotFoundError,
)
from netvoyager_intelligence.evidence import (
    EvidenceRecord,
    EvidenceRelation,
)


logger = get_logger(__name__)


class SqlEvidenceRepository:
    """Persist and retrieve evidence using SQLAlchemy.

    The repository preserves evidence identity and stores relations
    independently of operational network relationships.

    It does not interpret provenance details, evaluate evidence
    strength, or perform device and prefix reconciliation.

    All operations use the Session provided by the Unit of Work.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the repository with a transaction-scoped session."""
        self._session = session

    def add(self, record: EvidenceRecord) -> None:
        """Insert a new evidence record without replacing existing data.

        Reject an existing evidence identity. Flush the insertion so
        database constraints are evaluated before transaction commit.
        """
        self._session.add(record)

        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code="storage.evidence_already_exists",
                message="Cannot insert a conflicting evidence record.",
                details={
                    "evidence_id": str(record.id),
                },
            ) from exc

        logger.debug(
            "Evidence record inserted",
            extra={
                "evidence_id": str(record.id),
                "source": record.source,
            },
        )

    def link(
        self,
        evidence_id: UUID,
        object_type: str,
        object_id: UUID,
    ) -> None:
        """Link existing evidence to a UUID-identified domain object.

        An identical relation is idempotent. A conflicting object type
        for the same evidence/object pair is rejected.

        Referenced domain objects are not validated here because the
        target identity belongs to a separate domain.
        """
        existing = self._session.get(
            EvidenceRelation,
            (evidence_id, object_id),
        )

        if existing is not None:
            if existing.object_type != object_type:
                raise RepositoryConflictError(
                    code="storage.evidence_relation_conflict",
                    message=(
                        "Evidence relation already exists "
                        "with a different object type."
                    ),
                    details={
                        "evidence_id": str(evidence_id),
                        "object_id": str(object_id),
                        "stored_object_type": existing.object_type,
                        "provided_object_type": object_type,
                    },
                )

            return

        if self.get(evidence_id) is None:
            raise RepositoryNotFoundError(
                code="storage.evidence_not_found",
                message="Cannot link evidence that does not exist.",
                details={
                    "evidence_id": str(evidence_id),
                },
            )

        relation = EvidenceRelation(
            evidence_id=evidence_id,
            object_type=object_type,
            object_id=object_id,
        )

        self._session.add(relation)

        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code="storage.evidence_relation_conflict",
                message="Cannot insert a conflicting evidence relation.",
                details={
                    "evidence_id": str(evidence_id),
                    "object_id": str(object_id),
                    "object_type": object_type,
                },
            ) from exc

        logger.debug(
            "Evidence linked to domain object",
            extra={
                "evidence_id": str(evidence_id),
                "object_id": str(object_id),
                "object_type": object_type,
            },
        )

    def get(
        self,
        evidence_id: UUID,
    ) -> EvidenceRecord | None:
        """Return the evidence record identified by UUID, if present."""
        return self._session.get(EvidenceRecord, evidence_id)

    def for_object(
        self,
        object_id: UUID,
        *,
        object_type: str | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        """Return evidence associated with an object UUID.

        An optional object-type filter provides additional validation
        without changing the primary UUID lookup behavior.
        """
        statement = (
            select(EvidenceRecord)
            .join(EvidenceRelation)
            .where(EvidenceRelation.object_id == object_id)
        )

        if object_type is not None:
            statement = statement.where(
                EvidenceRelation.object_type == object_type
            )

        statement = statement.order_by(
            EvidenceRecord.created_at,
            EvidenceRecord.id,
        )

        return tuple(self._session.scalars(statement).all())

    def for_objects(
        self,
        object_ids: Iterable[UUID],
    ) -> tuple[EvidenceRecord, ...]:
        """Return distinct evidence linked to any supplied object UUID.

        Each evidence record is returned once, even when it is linked
        to multiple requested objects.
        """
        identifiers = tuple(set(object_ids))

        if not identifiers:
            return ()

        statement = (
            select(EvidenceRecord)
            .join(EvidenceRelation)
            .where(EvidenceRelation.object_id.in_(identifiers))
            .distinct()
            .order_by(
                EvidenceRecord.created_at,
                EvidenceRecord.id,
            )
        )

        return tuple(self._session.scalars(statement).all())

    def relations_for_object(
        self,
        object_id: UUID,
    ) -> tuple[EvidenceRelation, ...]:
        """Return evidence relations belonging to an object UUID."""
        statement = (
            select(EvidenceRelation)
            .where(EvidenceRelation.object_id == object_id)
            .order_by(EvidenceRelation.evidence_id)
        )

        return tuple(self._session.scalars(statement).all())
