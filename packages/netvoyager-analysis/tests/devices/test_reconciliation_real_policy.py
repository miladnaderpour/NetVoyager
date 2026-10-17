"""Integration of device reconciliation with the actual PolicyEngine.

Unlike test_reconciliation.py, this module does not use a fake policy.
"""

from uuid import uuid4

import pytest

from netvoyager_network.device.models import NetworkDevice
from netvoyager_analysis.devices.candidate_matching import IdentityTarget
from netvoyager_analysis.devices.discovery.models import DeviceDiscoveryCandidate
from netvoyager_analysis.devices.discovery.store import DeviceDiscoveryStore
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.devices.reconciliation import DeviceReconciliationService
from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.policies.models import (
    ClaimActionPolicy,
    ClaimPolicy,
    SourceProfile,
    SourceTrustPolicy,
)

PANORAMA = SourceRef("paloalto_panorama", "managed_device_inventory")
EXCEL = SourceRef("excel_inventory", "device_inventory")


def make_engine(*, allow_creation: bool = True, allow_promotion: bool = True) -> PolicyEngine:
    """Register a real typed trust policy for the Panorama physical-identity claim."""
    actions = []
    requirements = ("unique_physical_serial", "unambiguous_device_match")
    if allow_creation:
        actions.append(ClaimActionPolicy(action="create_canonical_device", requirements=requirements))
    if allow_promotion:
        actions.append(ClaimActionPolicy(action="promote_candidate", requirements=requirements))

    engine = PolicyEngine()
    engine.register(SourceTrustPolicy(
        profile=SourceProfile(
            source_id=PANORAMA.source_id,
            method=PANORAMA.method,
            description="Panorama managed physical firewall inventory",
        ),
        version=7,
        claims=(ClaimPolicy(
            claim="device.physical_identity",
            authority="trusted",
            actions=tuple(actions),
        ),),
    ))
    return engine


def fixture_entities():
    store = DeviceDiscoveryStore()
    excel = DeviceDiscoveryCandidate(name="Inventory firewall", serial_number="12345")
    store.add_candidate(excel)
    panorama = DeviceDiscoveryCandidate(name="PAN-020-Main", serial_number="0012345")
    sources = {excel.candidate_id: EXCEL}
    return store, excel, IdentityTarget(panorama, PANORAMA), sources


def reconcile(engine: PolicyEngine, store: DeviceDiscoveryStore, observed: IdentityTarget,
              sources: dict, devices: dict, *, name: str = "PAN-020-Main"):
    return DeviceReconciliationService(discovery_store=store, policy_engine=engine).reconcile(
        observed,
        canonical_devices=devices,
        evidence_ids=(uuid4(),),
        candidate_sources=sources,
        name=name,
    )


def test_real_policy_creates_canonical_and_resolves_excel_candidate():
    store, excel, observed, sources = fixture_entities()
    devices = {}
    result = reconcile(make_engine(), store, observed, sources, devices)
    assert result.created is True
    assert result.device.device_id in devices
    assert store.get_candidate(excel.candidate_id).resolved_device_id == result.device.device_id
    decisions = store.decisions_for(excel.candidate_id)
    assert len(decisions) == 1
    assert decisions[0].source_id == PANORAMA.source_id
    assert decisions[0].method == PANORAMA.method
    assert decisions[0].policy_version == 7


def test_real_policy_reuses_existing_canonical_device():
    store, excel, observed, sources = fixture_entities()
    existing = NetworkDevice(name="Existing", serial_number="0012345")
    devices = {existing.device_id: existing}
    result = reconcile(make_engine(), store, observed, sources, devices)
    assert result.created is False
    assert result.device is existing
    assert len(devices) == 1
    assert store.get_candidate(excel.candidate_id).resolved_device_id == existing.device_id


def test_real_policy_denies_canonical_creation_without_action():
    store, excel, observed, sources = fixture_entities()
    devices = {}
    with pytest.raises(PermissionError):
        reconcile(make_engine(allow_creation=False), store, observed, sources, devices)
    assert devices == {}
    assert store.get_candidate(excel.candidate_id).resolved_device_id is None
    assert store.decisions == ()


def test_real_policy_denies_candidate_resolution_without_promotion_action():
    store, excel, observed, sources = fixture_entities()
    devices = {}
    with pytest.raises(PermissionError):
        reconcile(make_engine(allow_promotion=False), store, observed, sources, devices)
    assert devices == {}
    assert store.get_candidate(excel.candidate_id).resolved_device_id is None
    assert store.decisions == ()


def test_unregistered_source_cannot_create_canonical_device():
    store, excel, observed, sources = fixture_entities()
    observed = IdentityTarget(observed.device, SourceRef("unknown_source", "unknown_method"))
    devices = {}
    with pytest.raises(PermissionError):
        reconcile(make_engine(), store, observed, sources, devices)
    assert devices == {}
    assert store.decisions == ()


def test_failed_physical_identity_validation_cannot_create_device():
    store, excel, observed, sources = fixture_entities()
    observed = IdentityTarget(DeviceDiscoveryCandidate(serial_number="unknown"), PANORAMA)
    devices = {}
    with pytest.raises(ValueError):
        reconcile(make_engine(), store, observed, sources, devices)
    assert devices == {}
    assert store.decisions == ()
