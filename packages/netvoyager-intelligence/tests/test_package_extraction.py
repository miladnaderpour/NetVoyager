"""Verify package ownership and migration import compatibility."""

from netvoyager_intelligence.evidence import EvidenceRecord, EvidenceStore
from netvoyager_intelligence.findings import Finding, FindingStore
from netvoyager_analysis.evidence.models import EvidenceRecord as OldEvidenceRecord
from netvoyager_analysis.evidence.store import EvidenceStore as OldEvidenceStore
from netvoyager_analysis.findings.models import Finding as OldFinding
from netvoyager_analysis.findings.store import FindingStore as OldFindingStore


def test_compatibility_imports_have_same_class_identity():
    assert EvidenceRecord is OldEvidenceRecord
    assert EvidenceStore is OldEvidenceStore
    assert Finding is OldFinding
    assert FindingStore is OldFindingStore


def test_stores_operate_without_database():
    evidence = EvidenceRecord(source="test", details={"row": 1})
    evidence_store = EvidenceStore()
    evidence_store.add(evidence)
    assert evidence_store.get(evidence.id) is evidence

    finding = Finding(kind="test", severity="warning", message="example")
    finding_store = FindingStore()
    finding_store.add(finding)
    assert finding_store.get(finding.id) is finding
