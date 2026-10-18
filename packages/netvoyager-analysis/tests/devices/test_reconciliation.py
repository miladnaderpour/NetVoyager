"""End-to-end identity admission and discovery candidate resolution."""
from dataclasses import dataclass
from uuid import uuid4

import pytest
from netvoyager_network.device.models import NetworkDevice
from netvoyager_analysis.devices.candidate_matching import IdentityTarget
from netvoyager_analysis.devices.discovery.models import DeviceDiscoveryCandidate
from netvoyager_analysis.devices.discovery.relationships import DeviceDiscoveryCandidateRelationship
from netvoyager_network.device.discovery.store import DeviceDiscoveryStore
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.devices.reconciliation import DeviceReconciliationService

PAN = SourceRef("paloalto_panorama", "managed_device_inventory")
EXCEL = SourceRef("excel_inventory", "device_inventory")

@dataclass(frozen=True)
class Authorized:
    allowed: bool = True
    reason: str = "allowed"
    policy_version: int = 1

class Policy:
    def __init__(self, allowed=True): self.allowed = allowed; self.calls = []
    def evaluate(self, source_id, method, *, claim, action, requirements):
        self.calls.append((source_id, method, claim, action, requirements))
        return Authorized(self.allowed)

def setup(serial="12345", pan_serial="0012345"):
    store = DeviceDiscoveryStore()
    excel = DeviceDiscoveryCandidate(name="Excel", serial_number=serial)
    store.add_candidate(excel)
    pan = DeviceDiscoveryCandidate(name="Firewall", serial_number=pan_serial)
    return store, excel, pan

def test_new_panorama_resolves_excel_candidate_without_merge():
    store, excel, pan = setup()
    devices = {}
    policy = Policy()
    result = DeviceReconciliationService(discovery_store=store, policy_engine=policy).reconcile(
        IdentityTarget(pan, PAN), canonical_devices=devices, evidence_ids=(uuid4(),),
        candidate_sources={excel.candidate_id: EXCEL}, name="PAN-020-Main",
    )
    assert result.created
    assert result.device.device_id in devices
    assert store.get_candidate(excel.candidate_id).resolved_device_id == result.device.device_id
    assert excel.candidate_id == store.get_candidate(excel.candidate_id).candidate_id
    assert store.decisions_for(excel.candidate_id)[0].policy_version == 1

def test_existing_canonical_device_is_reused():
    store, excel, pan = setup("12345", "0012345")
    existing = NetworkDevice(name="existing", serial_number="0012345")
    devices = {existing.device_id: existing}
    result = DeviceReconciliationService(discovery_store=store, policy_engine=Policy()).reconcile(
        IdentityTarget(pan, PAN), canonical_devices=devices, evidence_ids=(uuid4(),),
        candidate_sources={excel.candidate_id: EXCEL},
    )
    assert not result.created
    assert result.device is existing
    assert len(devices) == 1

def test_policy_denial_has_no_side_effects():
    store, excel, pan = setup()
    devices = {}
    with pytest.raises(PermissionError):
        DeviceReconciliationService(discovery_store=store, policy_engine=Policy(False)).reconcile(
            IdentityTarget(pan, PAN), canonical_devices=devices, evidence_ids=(uuid4(),),
            candidate_sources={excel.candidate_id: EXCEL}, name="PAN-020-Main",
        )
    assert not devices and not store.decisions
    assert store.get_candidate(excel.candidate_id).status == "candidate"

def test_conflicting_canonical_serial_prevents_creation():
    store, excel, pan = setup()
    a = NetworkDevice(name="A", serial_number="0012345")
    b = NetworkDevice(name="B", serial_number="0012345")
    devices = {a.device_id:a, b.device_id:b}
    with pytest.raises(ValueError):
        DeviceReconciliationService(discovery_store=store, policy_engine=Policy()).reconcile(
            IdentityTarget(pan, PAN), canonical_devices=devices, evidence_ids=(uuid4(),),
            candidate_sources={excel.candidate_id: EXCEL}, name="new",
        )
    assert len(devices) == 2 and not store.decisions

def test_missing_evidence_references_block_decision():
    store, excel, pan = setup()
    with pytest.raises(ValueError):
        DeviceReconciliationService(discovery_store=store, policy_engine=Policy()).reconcile(
            IdentityTarget(pan, PAN), canonical_devices={}, evidence_ids=(), name="New",
        )

def test_rejected_candidate_relation_prevents_joint_resolution():
    store, first, pan = setup()
    second = DeviceDiscoveryCandidate(serial_number="12345")
    store.add_candidate(second)
    relation = DeviceDiscoveryCandidateRelationship(first.candidate_id, second.candidate_id)
    store.add_relationship(relation)
    store.set_relationship_status(relation.relationship_id, "rejected", evidence_ids=(uuid4(),), reason="distinct chassis")
    devices = {}
    with pytest.raises(ValueError, match="Rejected"):
        DeviceReconciliationService(discovery_store=store, policy_engine=Policy()).reconcile(
            IdentityTarget(pan, PAN), canonical_devices=devices, evidence_ids=(uuid4(),),
            candidate_sources={first.candidate_id: EXCEL, second.candidate_id: EXCEL}, name="New",
        )
    assert not devices and store.get_candidate(first.candidate_id).resolved_device_id is None
