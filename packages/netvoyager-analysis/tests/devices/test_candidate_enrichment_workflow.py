
"""Tests for candidate enrichment persistence orchestration.

Uses synthetic observations and in-memory repository doubles.
"""

from netvoyager_analysis.devices.candidate_enrichment_workflow import (
    persist_candidate_enrichment,
)
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.devices.observations import DeviceObservation
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


SOURCE = SourceRef(
    source_id="test_inventory",
    method="device_inventory",
)


class CandidateRepository:
    def __init__(self):
        self.saved = []

    def save_candidate(self, candidate):
        self.saved.append(candidate)


class FindingRepository:
    def __init__(self):
        self.records = []

    def for_object(self, object_id, *, object_type=None):
        return tuple(
            finding
            for finding in self.records
            if finding.object_id == object_id
            and (
                object_type is None
                or finding.object_type == object_type
            )
        )

    def add(self, finding):
        self.records.append(finding)


def candidate(**attributes):
    return DeviceDiscoveryCandidate(
        name="SW-LAB-01",
        serial_number="TEST-001",
        **attributes,
    )


def observation(**attributes):
    return DeviceObservation(
        local_ref="test:row:1",
        inventory_name="SW-LAB-01",
        serial_number="TEST-001",
        **attributes,
    )


def apply(current, incoming, candidates, findings, *, dry_run=False):
    return persist_candidate_enrichment(
        current,
        incoming,
        source=SOURCE,
        candidates=candidates,
        findings=findings,
        dry_run=dry_run,
    )


def test_enrichment_saves_candidate_without_finding():
    candidates = CandidateRepository()
    findings = FindingRepository()

    original = candidate()
    result = apply(
        original,
        observation(site="LAB-A", model="Example Switch"),
        candidates,
        findings,
    )

    assert result.candidate.candidate_id == original.candidate_id
    assert result.candidate.site == "LAB-A"
    assert result.candidate.model == "Example Switch"
    assert len(candidates.saved) == 1
    assert findings.records == []


def test_repeated_conflict_does_not_duplicate_finding():
    candidates = CandidateRepository()
    findings = FindingRepository()

    original = candidate(site="LAB-A")
    first = apply(
        original,
        observation(site="LAB-B"),
        candidates,
        findings,
    )

    # This is a new observation instance with a different UUID.
    second = apply(
        original,
        observation(site="LAB-B"),
        candidates,
        findings,
    )

    assert first.candidate.site == "LAB-A"
    assert second.candidate.site == "LAB-A"
    assert len(first.new_findings) == 1
    assert len(second.new_findings) == 0
    assert second.duplicate_findings == 1
    assert len(findings.records) == 1
    assert candidates.saved == []


def test_new_conflict_value_creates_another_finding():
    candidates = CandidateRepository()
    findings = FindingRepository()

    original = candidate(site="LAB-A")

    apply(
        original,
        observation(site="LAB-B"),
        candidates,
        findings,
    )

    result = apply(
        original,
        observation(site="LAB-C"),
        candidates,
        findings,
    )

    assert len(result.new_findings) == 1
    assert len(findings.records) == 2


def test_dry_run_does_not_write():
    candidates = CandidateRepository()
    findings = FindingRepository()

    original = candidate(site="LAB-A")

    result = apply(
        original,
        observation(site="LAB-B", model="Example Switch"),
        candidates,
        findings,
        dry_run=True,
    )

    assert result.candidate.site == "LAB-A"
    assert result.candidate.model == "Example Switch"
    assert len(result.new_findings) == 1
    assert candidates.saved == []
    assert findings.records == []
