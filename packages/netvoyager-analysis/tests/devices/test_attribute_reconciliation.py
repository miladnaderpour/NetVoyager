"""Hostname assertion reconciliation with the real policy engine."""

from uuid import uuid4

from netvoyager_network.device.models import NetworkDevice
from netvoyager_analysis.attributes.store import AttributeAssertionStore
from netvoyager_analysis.devices.attribute_reconciliation import (
    DeviceAttributeReconciliationService,
)
from netvoyager_analysis.devices.identity_validation import IdentityValidationResult
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.evidence.models import EvidenceRecord
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.policies.models import (
    ClaimActionPolicy, ClaimPolicy, SourceProfile, SourceTrustPolicy,
)

PAN = SourceRef("paloalto_panorama", "managed_device_inventory")
VALID = IdentityValidationResult(
    status="verified", reason="Verified physical serial",
    valid_physical_serial=True, unique_physical_serial=True,
    unambiguous_device_match=True,
)
INVALID = IdentityValidationResult(status="unresolved", reason="Weak match")


def make_service(*, allow_confirmation=True):
    evidence = EvidenceStore()
    assertions = AttributeAssertionStore(evidence_store=evidence)
    policy = PolicyEngine()
    policy.register(SourceTrustPolicy(
        profile=SourceProfile(
            source_id=PAN.source_id, method=PAN.method,
            description="Physical firewall inventory",
        ),
        version=7,
        claims=(ClaimPolicy(
            claim="device.host_name", authority="trusted",
            actions=(ClaimActionPolicy(
                action="confirm_attribute",
                requirements=("verified_device_identity",),
            ),) if allow_confirmation else (),
        ),),
    ))
    service = DeviceAttributeReconciliationService(
        assertion_store=assertions, policy_engine=policy,
    )
    return service, evidence, assertions


def observed_evidence(store):
    record = EvidenceRecord(source=PAN.source_id, details={"host_name": "PAN-MAN"})
    store.add(record)
    return (record.id,)


def test_confirmed_assertion_does_not_mutate_canonical_device():
    service, evidence, assertions = make_service()
    device = NetworkDevice(name="Firewall", serial_number="0012345")
    ids = observed_evidence(evidence)
    result = service.reconcile_host_name(
        device, "PAN-MAN", source=PAN, evidence_ids=ids, identity=VALID,
    )
    assert result.status == "confirmed"
    assert device.host_name is None
    assertion = assertions.get(result.assertion_id)
    assert assertion.status == "confirmed"
    assert assertion.value == "PAN-MAN"
    assert assertions.decisions_for(result.assertion_id)[0].policy_version == 7


def test_policy_denial_keeps_proposed_claim():
    service, evidence, assertions = make_service(allow_confirmation=False)
    device = NetworkDevice(name="Firewall")
    result = service.reconcile_host_name(
        device, "PAN-MAN", source=PAN,
        evidence_ids=observed_evidence(evidence), identity=VALID,
    )
    assert result.status == "proposed"
    assert assertions.get(result.assertion_id).status == "proposed"
    assert not assertions.decisions


def test_existing_different_hostname_is_not_overwritten():
    service, evidence, assertions = make_service()
    device = NetworkDevice(name="Firewall", host_name="EXCEL-FW")
    result = service.reconcile_host_name(
        device, "PAN-MAN", source=PAN,
        evidence_ids=observed_evidence(evidence), identity=VALID,
    )
    assert result.status == "conflict"
    assert device.host_name == "EXCEL-FW"
    assert assertions.get(result.assertion_id).status == "proposed"


def test_unverified_identity_cannot_create_assertion():
    service, evidence, assertions = make_service()
    device = NetworkDevice(name="Firewall")
    result = service.reconcile_host_name(
        device, "PAN-MAN", source=PAN,
        evidence_ids=observed_evidence(evidence), identity=INVALID,
    )
    assert result.status == "denied"
    assert not assertions.assertions


def test_repeated_observation_reuses_existing_assertion():
    service, evidence, assertions = make_service()
    device = NetworkDevice(name="Firewall")
    first = service.reconcile_host_name(
        device, "PAN-MAN", source=PAN,
        evidence_ids=observed_evidence(evidence), identity=VALID,
    )
    second = service.reconcile_host_name(
        device, "PAN-MAN", source=PAN,
        evidence_ids=observed_evidence(evidence), identity=VALID,
    )
    assert second.status == "unchanged"
    assert first.assertion_id == second.assertion_id
    assert len(assertions.assertions) == 1
    assert len(assertions.get(first.assertion_id).evidence_ids) == 2


def test_missing_evidence_references_rejected():
    service, evidence, assertions = make_service()
    device = NetworkDevice(name="Firewall")
    import pytest
    with pytest.raises(KeyError):
        service.reconcile_host_name(
            device, "PAN-MAN", source=PAN,
            evidence_ids=(uuid4(),), identity=VALID,
        )
    assert not assertions.assertions


def test_unregistered_source_retains_unconfirmed_claim():
    service, evidence, assertions = make_service()
    device = NetworkDevice(name="Firewall")
    result = service.reconcile_host_name(
        device, "PAN-MAN", source=SourceRef("unregistered", "other"),
        evidence_ids=observed_evidence(evidence), identity=VALID,
    )
    assert result.status == "proposed"
    assert assertions.get(result.assertion_id).status == "proposed"
