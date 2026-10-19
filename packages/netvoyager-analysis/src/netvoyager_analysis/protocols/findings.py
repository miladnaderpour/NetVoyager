
"""Storage-independent repository contract for analysis findings."""

from typing import Protocol
from uuid import UUID

from netvoyager_intelligence.findings import Finding


class FindingRepositoryProtocol(Protocol):
    """Provide persistence and retrieval of analysis findings.

    Finding creation and interpretation belong to analysis workflows.
    Repository implementations perform storage operations without
    controlling transactions or evaluating domain policies.
    """

    def add(self, finding: Finding) -> None:
        """Persist a new finding without replacing an existing identity."""
        ...

    def get(self, finding_id: UUID) -> Finding | None:
        """Return a finding by UUID, or None if it does not exist."""
        ...

    def for_object(
        self,
        object_id: UUID,
        *,
        object_type: str | None = None,
    ) -> tuple[Finding, ...]:
        """Return findings for a domain object in chronological order."""
        ...

    def find_by_kind(
        self,
        kind: str,
    ) -> tuple[Finding, ...]:
        """Return findings matching an exact classification."""
        ...
