"""In-memory storage and lookup of evidence and object relations."""

from uuid import UUID

from .models import EvidenceRecord, EvidenceRelation


class EvidenceStore:
    """Store evidence by ID and link it to network objects.

    Records are retained by reference. Object IDs are supplied by callers;
    the store does not check whether the network objects exist.
    """

    def __init__(self) -> None:
        self._records: dict[UUID, EvidenceRecord] = {}
        self._relations: set[EvidenceRelation] = set()

    def add(self, record: EvidenceRecord) -> None:
        """Add evidence, raising ValueError if its ID already exists."""
        if record.id in self._records:
            raise ValueError(f"Evidence already exists: {record.id}")

        self._records[record.id] = record

    def link(
        self,
        evidence_id: UUID,
        object_type: str,
        object_id: UUID | str,
    ) -> None:
        """Link existing evidence to an object.

        Raise KeyError if the evidence does not exist.
        Repeating an existing link has no effect.
        """
        if evidence_id not in self._records:
            raise KeyError(evidence_id)

        self._relations.add(
            EvidenceRelation(
                evidence_id=evidence_id,
                object_type=object_type,
                object_id=object_id,
            )
        )

    def get(self, evidence_id: UUID) -> EvidenceRecord:
        """Return evidence by ID, raising KeyError when absent."""
        return self._records[evidence_id]

    def for_object(
        self,
        object_type: str,
        object_id: UUID | str,
    ) -> tuple[EvidenceRecord, ...]:
        """Return linked evidence in record insertion order.

        Return an empty tuple when the object has no linked evidence.
        """
        evidence_ids = {
            relation.evidence_id
            for relation in self._relations
            if relation.object_type == object_type
            and relation.object_id == object_id
        }

        return tuple(
            record
            for evidence_id, record in self._records.items()
            if evidence_id in evidence_ids
        )

    @property
    def records(self) -> tuple[EvidenceRecord, ...]:
        """Return all records in insertion order."""
        return tuple(self._records.values())

    @property
    def relations(self) -> frozenset[EvidenceRelation]:
        """Return an immutable snapshot of all links."""
        return frozenset(self._relations)