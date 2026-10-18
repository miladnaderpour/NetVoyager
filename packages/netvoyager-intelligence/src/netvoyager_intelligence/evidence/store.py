
"""In-memory storage and lookup of evidence and object relations."""

from collections.abc import Iterable
from uuid import UUID

from .models import EvidenceRecord, EvidenceRelation


EvidenceObjectKey = tuple[str, UUID | str]


class EvidenceStore:
    """Store evidence by ID and link it to network objects.

    Records are retained by reference. Object IDs are supplied by callers;
    the store does not check whether the network objects exist.

    Object-to-evidence indexes provide efficient reverse lookup without
    using evidence relationships for operational domain reconciliation.

    Evidence retrieval preserves record insertion order, including when
    records are linked to an object after their initial creation.
    """

    def __init__(self) -> None:
        self._records: dict[UUID, EvidenceRecord] = {}
        self._relations: set[EvidenceRelation] = set()

        self._record_order: dict[UUID, int] = {}

        self._object_evidence: dict[
            EvidenceObjectKey,
            set[UUID],
        ] = {}

    def add(self, record: EvidenceRecord) -> None:
        """Add evidence, raising ValueError if its ID already exists."""
        if record.id in self._records:
            raise ValueError(f"Evidence already exists: {record.id}")

        self._record_order[record.id] = len(self._records)
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

        Update the object-to-evidence reverse index while preserving
        the original evidence record and existing relationships.
        """
        if evidence_id not in self._records:
            raise KeyError(evidence_id)

        relation = EvidenceRelation(
            evidence_id=evidence_id,
            object_type=object_type,
            object_id=object_id,
        )

        if relation in self._relations:
            return

        self._relations.add(relation)

        key = (object_type, object_id)

        self._object_evidence.setdefault(
            key,
            set(),
        ).add(evidence_id)

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
        key = (object_type, object_id)

        evidence_ids = self._object_evidence.get(
            key,
            set(),
        )

        return self._ordered_records(evidence_ids)

    def for_objects(
        self,
        objects: Iterable[EvidenceObjectKey],
    ) -> tuple[EvidenceRecord, ...]:
        """Return evidence linked to any of the supplied objects.

        Duplicate evidence references are returned only once.

        Evidence is ordered by its original insertion into the store,
        regardless of the order of the supplied objects.

        This method does not infer relationships between domain objects.
        Callers must supply the complete collection of object identities.
        """
        evidence_ids: set[UUID] = set()

        for key in objects:
            evidence_ids.update(
                self._object_evidence.get(
                    key,
                    set(),
                )
            )

        return self._ordered_records(evidence_ids)

    def _ordered_records(
        self,
        evidence_ids: Iterable[UUID],
    ) -> tuple[EvidenceRecord, ...]:
        """Return indexed evidence sorted by original record insertion."""
        ordered_ids = sorted(
            evidence_ids,
            key=self._record_order.__getitem__,
        )

        return tuple(
            self._records[evidence_id]
            for evidence_id in ordered_ids
        )

    @property
    def records(self) -> tuple[EvidenceRecord, ...]:
        """Return all records in insertion order."""
        return tuple(self._records.values())

    @property
    def relations(self) -> frozenset[EvidenceRelation]:
        """Return an immutable snapshot of all links."""
        return frozenset(self._relations)
