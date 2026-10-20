
"""Tests for evidence-backed attribute assertion storage and decisions."""

from ipaddress import IPv4Address
from uuid import UUID, uuid4

import pytest

from netvoyager_analysis.attributes.models import AttributeAssertion
from netvoyager_analysis.attributes.store import AttributeAssertionStore
from netvoyager_analysis.protocols.evidence import EvidenceRepositoryProtocol
from netvoyager_database.engine import create_database_engine
from netvoyager_database.repositories.evidence import SqlEvidenceRepository
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_intelligence.evidence import EvidenceRecord
from netvoyager_analysis.policies.models import PolicyEvaluationResult


@pytest.fixture
def evidence_store():
    """Provide an isolated SQLite-backed evidence repository."""
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            yield SqlEvidenceRepository(session)
    finally:
        engine.dispose()


@pytest.fixture
def assertion_store(
    evidence_store: EvidenceRepositoryProtocol,
) -> AttributeAssertionStore:
    """Return an assertion store linked to the evidence store."""
    return AttributeAssertionStore(
        evidence_store=evidence_store,
    )


@pytest.fixture
def device_id() -> UUID:
    """Return a stable identity for one test device."""
    return uuid4()


def add_evidence(
    store: EvidenceRepositoryProtocol,
    *,
    source: str = "excel_inventory",
    value: str = "SW01",
) -> EvidenceRecord:
    """Create and register an attribute observation."""
    record = EvidenceRecord(
        source=source,
        details={
            "field_name": "host_name",
            "observed_value": value,
        },
    )

    store.add(record)
    return record


def make_assertion(
    target_id: UUID,
    evidence_id: UUID,
    *,
    field_name: str = "host_name",
    value: str = "SW01",
) -> AttributeAssertion:
    """Construct one proposed device attribute assertion."""
    return AttributeAssertion(
        target_type="network_device",
        target_id=target_id,
        field_name=field_name,
        value=value,
        evidence_ids=(evidence_id,),
    )


def allowed_policy(
    *,
    claim: str = "device.host_name",
    action: str = "confirm_attribute",
    allowed: bool = True,
) -> PolicyEvaluationResult:
    """Return a simulated policy evaluation result."""
    return PolicyEvaluationResult(
        source_id="paloalto_panorama",
        method="managed_device_inventory",
        policy_version=1,
        claim=claim,
        action=action,
        status="allowed" if allowed else "denied",
        authority="trusted",
        reason=None if allowed else "Policy denied the action",
    )


def confirm_assertion(
    store: AttributeAssertionStore,
    assertion_id: UUID,
    evidence_id: UUID,
    *,
    policy_result: PolicyEvaluationResult | None = None,
) -> AttributeAssertion:
    """Confirm an assertion using simulated policy authorization."""
    return store.transition(
        assertion_id,
        "confirmed",
        evidence_ids=(evidence_id,),
        source_id="paloalto_panorama",
        method="managed_device_inventory",
        policy_version=1,
        policy_result=(
            policy_result
            if policy_result is not None
            else allowed_policy()
        ),
    )


def test_register_proposed_assertion(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Register an assertion and link its original evidence."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    assert assertion_store.get(assertion.assertion_id) == assertion
    assert assertion_store.assertions == (assertion,)

    assert evidence_store.for_object(
        assertion.assertion_id,
        object_type="attribute_assertion",
    ) == (evidence,)


def test_reject_missing_evidence(
    assertion_store: AttributeAssertionStore,
    device_id: UUID,
) -> None:
    """An assertion cannot reference nonexistent evidence."""
    assertion = make_assertion(device_id, uuid4())

    with pytest.raises(KeyError):
        assertion_store.add(assertion)

    assert assertion_store.assertions == ()


def test_reject_duplicate_assertion_identity(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """An assertion UUID cannot be registered twice."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    with pytest.raises(ValueError, match="already exists"):
        assertion_store.add(assertion)


def test_reject_duplicate_logical_claim(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """The same target, field, and value cannot be registered twice."""
    first = add_evidence(evidence_store)
    second = add_evidence(
        evidence_store,
        source="paloalto_panorama",
    )

    assertion_store.add(make_assertion(device_id, first.id))

    with pytest.raises(ValueError, match="already exists"):
        assertion_store.add(
            make_assertion(device_id, second.id)
        )

    assert len(assertion_store.assertions) == 1


def test_distinct_values_can_coexist(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Conflicting observed values remain separate assertions."""
    first = add_evidence(evidence_store, value="SW01")
    second = add_evidence(evidence_store, value="MAN-SW01")

    assertion_store.add(
        make_assertion(device_id, first.id, value="SW01")
    )
    assertion_store.add(
        make_assertion(device_id, second.id, value="MAN-SW01")
    )

    assertions = assertion_store.for_field(
        "network_device",
        device_id,
        "host_name",
    )

    assert len(assertions) == 2
    assert {item.value for item in assertions} == {
        "SW01",
        "MAN-SW01",
    }


def test_add_evidence_without_status_change(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Additional evidence does not automatically confirm an assertion."""
    excel = add_evidence(evidence_store)
    panorama = add_evidence(
        evidence_store,
        source="paloalto_panorama",
    )

    assertion = make_assertion(device_id, excel.id)
    assertion_store.add(assertion)

    updated = assertion_store.add_evidence(
        assertion.assertion_id,
        panorama.id,
    )

    assert updated.evidence_ids == (excel.id, panorama.id)
    assert updated.status == "proposed"
    assert assertion_store.decisions == ()

    assert evidence_store.for_object(
        assertion.assertion_id,
        object_type="attribute_assertion",
    ) == (excel, panorama)


def test_repeated_evidence_is_idempotent(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Linking the same evidence again must not duplicate it."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    updated = assertion_store.add_evidence(
        assertion.assertion_id,
        evidence.id,
    )

    assert updated.evidence_ids == (evidence.id,)
    assert len(assertion_store.assertions) == 1


def test_confirm_with_allowed_policy(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """An authorized confirmation updates status and records a decision."""
    evidence = add_evidence(
        evidence_store,
        source="paloalto_panorama",
    )
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    updated = confirm_assertion(
        assertion_store,
        assertion.assertion_id,
        evidence.id,
    )

    assert updated.status == "confirmed"

    decisions = assertion_store.decisions_for(
        assertion.assertion_id
    )

    assert len(decisions) == 1
    assert decisions[0].previous_status == "proposed"
    assert decisions[0].new_status == "confirmed"
    assert decisions[0].evidence_ids == (evidence.id,)
    assert decisions[0].source_id == "paloalto_panorama"
    assert decisions[0].policy_version == 1


def test_confirmation_requires_authorization(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """A denied policy result cannot confirm an assertion."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    with pytest.raises(ValueError, match="policy authorization"):
        confirm_assertion(
            assertion_store,
            assertion.assertion_id,
            evidence.id,
            policy_result=allowed_policy(allowed=False),
        )

    assert assertion_store.get(
        assertion.assertion_id
    ).status == "proposed"

    assert assertion_store.decisions == ()


def test_reject_mismatching_policy_claim(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """An authorization for another attribute cannot confirm this one."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    with pytest.raises(ValueError, match="does not match"):
        confirm_assertion(
            assertion_store,
            assertion.assertion_id,
            evidence.id,
            policy_result=allowed_policy(
                claim="device.serial_number",
            ),
        )

    assert assertion_store.decisions == ()


def test_dispute_preserves_decision_history(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """A confirmed assertion can be disputed without losing its history."""
    first = add_evidence(evidence_store)
    second = add_evidence(
        evidence_store,
        source="paloalto_panorama",
        value="SW02",
    )

    assertion = make_assertion(device_id, first.id)
    assertion_store.add(assertion)

    confirm_assertion(
        assertion_store,
        assertion.assertion_id,
        first.id,
    )

    disputed = assertion_store.transition(
        assertion.assertion_id,
        "disputed",
        evidence_ids=(second.id,),
        source_id="paloalto_panorama",
        method="managed_device_inventory",
        policy_version=1,
        reason="Conflicting hostname observation",
    )

    assert disputed.status == "disputed"

    decisions = assertion_store.decisions_for(
        assertion.assertion_id
    )

    assert len(decisions) == 2
    assert decisions[0].new_status == "confirmed"
    assert decisions[1].previous_status == "confirmed"
    assert decisions[1].new_status == "disputed"
    assert decisions[1].reason == "Conflicting hostname observation"


def test_dispute_requires_reason(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """A dispute cannot be recorded without an explanation."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    with pytest.raises(ValueError, match="require a reason"):
        assertion_store.transition(
            assertion.assertion_id,
            "disputed",
            evidence_ids=(evidence.id,),
            source_id="excel_inventory",
            method="device_inventory",
            policy_version=1,
        )

    assert assertion_store.decisions == ()


def test_supersession_preserves_history(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Superseded assertions remain queryable with all decisions."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    confirm_assertion(
        assertion_store,
        assertion.assertion_id,
        evidence.id,
    )

    updated = assertion_store.transition(
        assertion.assertion_id,
        "superseded",
        evidence_ids=(evidence.id,),
        source_id="paloalto_panorama",
        method="managed_device_inventory",
        policy_version=1,
        reason="Hostname replaced by a newer confirmed value",
    )

    assert updated.status == "superseded"
    assert len(assertion_store.decisions_for(
        assertion.assertion_id
    )) == 2

    with pytest.raises(ValueError, match="Invalid attribute transition"):
        confirm_assertion(
            assertion_store,
            assertion.assertion_id,
            evidence.id,
        )


def test_returned_assertion_snapshots_are_immutable(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Older assertion snapshots remain unchanged after a transition."""
    evidence = add_evidence(evidence_store)
    assertion = make_assertion(device_id, evidence.id)

    assertion_store.add(assertion)

    original = assertion_store.get(assertion.assertion_id)

    updated = confirm_assertion(
        assertion_store,
        assertion.assertion_id,
        evidence.id,
    )

    assert original.status == "proposed"
    assert updated.status == "confirmed"
    assert original is not updated


def test_assertion_lookup_is_target_specific(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Different target identities retain independent assertions."""
    evidence = add_evidence(evidence_store)

    canonical = make_assertion(device_id, evidence.id)

    candidate = AttributeAssertion(
        target_type="device_discovery_candidate",
        target_id=uuid4(),
        field_name="host_name",
        value="SW01",
        evidence_ids=(evidence.id,),
    )

    assertion_store.add(canonical)
    assertion_store.add(candidate)

    assert assertion_store.for_target(
        "network_device",
        device_id,
    ) == (canonical,)

    assert assertion_store.for_target(
        "device_discovery_candidate",
        candidate.target_id,
    ) == (candidate,)


def test_find_value_preserves_value_types(
    assertion_store: AttributeAssertionStore,
    evidence_store: EvidenceRepositoryProtocol,
    device_id: UUID,
) -> None:
    """Exact attribute lookup preserves the original value type."""
    evidence = add_evidence(evidence_store)

    assertion = AttributeAssertion(
        target_type="network_device",
        target_id=device_id,
        field_name="management_ip",
        value=IPv4Address("192.0.2.15"),
        evidence_ids=(evidence.id,),
    )

    assertion_store.add(assertion)

    assert assertion_store.find_value(
        "network_device",
        device_id,
        "management_ip",
        IPv4Address("192.0.2.15"),
    ) == assertion

    assert assertion_store.find_value(
        "network_device",
        device_id,
        "management_ip",
        "192.0.2.15",
    ) is None
