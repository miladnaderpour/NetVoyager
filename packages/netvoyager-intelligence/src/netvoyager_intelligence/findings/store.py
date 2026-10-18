"""Storage for analysis findings."""

from collections import defaultdict
from uuid import UUID

from .models import Finding


class FindingStore:
    """In-memory store for analysis findings."""

    def __init__(self) -> None:
        self._findings: dict[UUID, Finding] = {}

    def add(self, finding: Finding) -> None:
        """Add a finding to the store."""
        if finding.id in self._findings:
            raise ValueError(
                f"Finding already exists: {finding.id}"
            )

        self._findings[finding.id] = finding

    def get(self, finding_id: UUID) -> Finding:
        """Return one finding by ID."""
        return self._findings[finding_id]

    def for_object(
        self,
        object_type: str,
        object_id: UUID | str,
    ) -> tuple[Finding, ...]:
        """Return findings related to one object."""
        return tuple(
            finding
            for finding in self._findings.values()
            if (
                finding.object_type == object_type
                and finding.object_id == object_id
            )
        )

    def by_kind(
        self,
        kind: str,
    ) -> tuple[Finding, ...]:
        """Return findings of one kind."""
        return tuple(
            finding
            for finding in self._findings.values()
            if finding.kind == kind
        )

    @property
    def findings(self) -> tuple[Finding, ...]:
        """Return all findings in insertion order."""
        return tuple(self._findings.values())