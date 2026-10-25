
"""Persist candidate enrichment and nonduplicate conflict findings.

The caller owns the transaction and supplies repository implementations.

Matching and canonical authorization are deliberately out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from netvoyager_analysis.devices.candidate_enrichment import (
    FINDING_KIND,
    enrich_device_candidate,
)
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.devices.observations import DeviceObservation
from netvoyager_intelligence.findings import Finding
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


class CandidateRepository(Protocol):
    """Persistence operations required for candidate enrichment."""

    def save_candidate(
        self,
        candidate: DeviceDiscoveryCandidate,
    ) -> None: ...


class FindingRepository(Protocol):
    """Persistence operations required for candidate conflict findings."""

    def for_object(
        self,
        object_id: UUID,
        *,
        object_type: str | None = None,
    ) -> tuple[Finding, ...]: ...

    def add(self, finding: Finding) -> None: ...


_CONFLICT_DETAIL_FIELDS = (
    "attribute",
    "existing_value",
    "incoming_value",
    "source_id",
    "source_method",
)


@dataclass(frozen=True, slots=True)
class CandidateEnrichmentPersistenceResult:
    """Result of enriching and optionally persisting one candidate."""

    candidate: DeviceDiscoveryCandidate
    changed_fields: tuple[str, ...]
    new_findings: tuple[Finding, ...]
    duplicate_findings: int


def _conflict_key(finding: Finding) -> tuple[object, ...]:
    """Identify a recurring conflict independently of observation UUID.

    The object identity, classification, compared field and source
    establish whether a conflict has already been recorded.
    """
    details = finding.details or {}

    return (
        finding.object_type,
        finding.object_id,
        finding.kind,
        *(details.get(field) for field in _CONFLICT_DETAIL_FIELDS),
    )


def persist_candidate_enrichment(
    candidate: DeviceDiscoveryCandidate,
    observation: DeviceObservation,
    *,
    source: SourceRef,
    candidates: CandidateRepository,
    findings: FindingRepository,
    dry_run: bool = False,
) -> CandidateEnrichmentPersistenceResult:
    """Enrich an existing candidate and persist changes and new findings.

    The caller must establish a unique candidate match first.

    Database operations participate in the caller's Unit of Work.
    This function neither commits nor rolls back transactions.
    """
    enrichment = enrich_device_candidate(
        candidate,
        observation,
        source=source,
    )

    existing_findings = findings.for_object(
        candidate.candidate_id,
        object_type="device_discovery_candidate",
    )

    known_keys = {
        _conflict_key(finding)
        for finding in existing_findings
        if finding.kind == FINDING_KIND
    }

    new_findings: list[Finding] = []
    duplicate_count = 0

    for finding in enrichment.findings:
        key = _conflict_key(finding)

        if key in known_keys:
            duplicate_count += 1
            continue

        known_keys.add(key)
        new_findings.append(finding)

    if not dry_run:
        if enrichment.changed_fields:
            candidates.save_candidate(enrichment.candidate)

        for finding in new_findings:
            findings.add(finding)

    return CandidateEnrichmentPersistenceResult(
        candidate=enrichment.candidate,
        changed_fields=enrichment.changed_fields,
        new_findings=tuple(new_findings),
        duplicate_findings=duplicate_count,
    )
