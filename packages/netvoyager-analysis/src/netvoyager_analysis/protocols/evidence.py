
"""Storage-independent repository contract for evidence provenance."""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from netvoyager_intelligence.evidence import (
    EvidenceRecord,
    EvidenceRelation,
)


class EvidenceRepositoryProtocol(Protocol):
    """Provide access to evidence records and their object associations.

    Evidence is retained for source provenance, not domain matching
    or reconciliation.

    Implementations must preserve evidence identities, support
    idempotent associations, and return results in record creation
    order.

    Transaction commit and rollback belong to the Unit of Work.
    """

    def add(self, record: EvidenceRecord) -> None:
        """Register a new evidence record without replacing an existing one."""
        ...

    def link(
        self,
        evidence_id: UUID,
        object_type: str,
        object_id: UUID,
    ) -> None:
        """Associate existing evidence with an identified domain object.

        An existing identical association has no effect. Conflicting
        object-type assignments for the same evidence/object pair
        must be rejected.
        """
        ...

    def get(self, evidence_id: UUID) -> EvidenceRecord | None:
        """Return evidence by UUID, or None when unavailable."""
        ...

    def for_object(
        self,
        object_id: UUID,
        *,
        object_type: str | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        """Return evidence for one object in record creation order."""
        ...

    def for_objects(
        self,
        object_ids: Iterable[UUID],
    ) -> tuple[EvidenceRecord, ...]:
        """Return distinct evidence associated with the supplied objects."""
        ...

    def relations_for_object(
        self,
        object_id: UUID,
    ) -> tuple[EvidenceRelation, ...]:
        """Return provenance associations referencing one object UUID."""
        ...
