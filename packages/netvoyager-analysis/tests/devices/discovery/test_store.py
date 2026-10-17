"""Focused tests for the non-destructive device discovery registry."""

from dataclasses import FrozenInstanceError
from ipaddress import IPv4Address
from uuid import uuid4

import pytest

from netvoyager_analysis.devices.discovery.models import DeviceDiscoveryCandidate
from netvoyager_analysis.devices.discovery.relationships import (
    DeviceDiscoveryCandidateRelationship,
)
from netvoyager_analysis.devices.discovery.store import DeviceDiscoveryStore


def registered(store: DeviceDiscoveryStore) -> DeviceDiscoveryCandidate:
    candidate = DeviceDiscoveryCandidate(name="FW-01")
    store.add_candidate(candidate)
    return candidate


def pair(store: DeviceDiscoveryStore):
    first, second = registered(store), registered(store)
    relation = DeviceDiscoveryCandidateRelationship(first.candidate_id, second.candidate_id)
    store.add_relationship(relation)
    return first, second, relation


def test_candidate_uuid_does_not_depend_on_name():
    a = DeviceDiscoveryCandidate(name="same")
    b = DeviceDiscoveryCandidate(name="same")
    assert a.candidate_id != b.candidate_id


def test_initial_candidate_must_be_unresolved():
    store = DeviceDiscoveryStore()
    candidate = DeviceDiscoveryCandidate(status="resolved", resolved_device_id=uuid4())
    with pytest.raises(ValueError, match="begin unresolved"):
        store.add_candidate(candidate)


def test_cannot_register_duplicate_candidate():
    store = DeviceDiscoveryStore()
    candidate = registered(store)
    with pytest.raises(ValueError, match="already exists"):
        store.add_candidate(candidate)


def test_candidate_snapshot_is_immutable():
    store = DeviceDiscoveryStore()
    candidate = registered(store)
    with pytest.raises(FrozenInstanceError):
        candidate.name = "changed"
    assert store.get_candidate(candidate.candidate_id).name == "FW-01"


def test_candidate_attribute_update_records_change_without_overwriting_snapshot():
    store = DeviceDiscoveryStore()
    before = registered(store)
    after = store.update_candidate_attributes(
        before.candidate_id,
        host_name="pan-fw",
        management_ip=IPv4Address("10.0.0.1"),
        evidence_ids=(uuid4(),),
        reason="Confirmed discovery values",
    )
    assert before.host_name is None
    assert after.host_name == "pan-fw"
    assert after.candidate_id == before.candidate_id
    assert after.management_ip == IPv4Address("10.0.0.1")
    assert store.decisions_for(before.candidate_id)[0].decision_type == "candidate_attributes"


def test_candidate_lifecycle_requires_reason_and_preserves_history():
    store = DeviceDiscoveryStore()
    candidate = registered(store)
    with pytest.raises(ValueError, match="reason"):
        store.set_candidate_status(candidate.candidate_id, "corroborated", evidence_ids=(uuid4(),), reason="")
    store.set_candidate_status(candidate.candidate_id, "corroborated", evidence_ids=(uuid4(),), reason="new signal")
    assert candidate.status == "candidate"
    assert store.get_candidate(candidate.candidate_id).status == "corroborated"
    assert store.decisions_for(candidate.candidate_id)[0].previous_value == "candidate"


def test_relationship_id_symmetric_and_stable():
    a, b = uuid4(), uuid4()
    first = DeviceDiscoveryCandidateRelationship(a, b)
    second = DeviceDiscoveryCandidateRelationship(b, a, status="rejected")
    assert first.relationship_id == second.relationship_id
    assert first.candidate_a_id == second.candidate_a_id


def test_relationship_snapshot_and_evidence_are_immutable():
    relation = DeviceDiscoveryCandidateRelationship(uuid4(), uuid4(), evidence_ids={uuid4()})
    assert isinstance(relation.evidence_ids, frozenset)
    with pytest.raises(FrozenInstanceError):
        relation.status = "confirmed"
    with pytest.raises(AttributeError):
        relation.evidence_ids.add(uuid4())


def test_reject_initial_confirmed_relationship():
    store = DeviceDiscoveryStore()
    a, b = registered(store), registered(store)
    relation = DeviceDiscoveryCandidateRelationship(a.candidate_id, b.candidate_id, status="confirmed")
    with pytest.raises(ValueError, match="start as possible"):
        store.add_relationship(relation)


def test_relationship_requires_known_candidates():
    store = DeviceDiscoveryStore()
    a = registered(store)
    relation = DeviceDiscoveryCandidateRelationship(a.candidate_id, uuid4())
    with pytest.raises(KeyError, match="Unknown candidate"):
        store.add_relationship(relation)


def test_relationship_index_and_reverse_lookup():
    store = DeviceDiscoveryStore()
    a, b, rel = pair(store)
    assert store.find_relationship(b.candidate_id, a.candidate_id) == rel
    assert store.relationships_for_candidate(a.candidate_id) == (rel,)
    assert store.relationships_for_candidate(b.candidate_id) == (rel,)


def test_relationship_status_change_and_reversal_are_audited():
    store = DeviceDiscoveryStore()
    _, _, original = pair(store)
    ev1, ev2 = uuid4(), uuid4()
    store.set_relationship_status(
        original.relationship_id, "confirmed", evidence_ids=(ev1,), reason="validated serial",
        source_id="paloalto_panorama", method="managed_device_inventory", policy_version=1,
    )
    confirmed = store.get_relationship(original.relationship_id)
    assert original.status == "possible"
    assert confirmed.status == "confirmed"
    assert confirmed.evidence_ids == frozenset({ev1})
    store.set_relationship_status(original.relationship_id, "possible", evidence_ids=(ev2,), reason="identity disputed")
    restored = store.get_relationship(original.relationship_id)
    assert restored.relationship_id == original.relationship_id
    assert restored.evidence_ids == frozenset({ev1, ev2})
    history = store.decisions_for(original.relationship_id)
    assert [(d.previous_value, d.new_value) for d in history] == [
        ("possible", "confirmed"), ("confirmed", "possible")
    ]
    assert history[0].source_id == "paloalto_panorama"
    assert history[0].policy_version == 1


def test_rejected_relationship_can_be_reconsidered():
    store = DeviceDiscoveryStore()
    _, _, rel = pair(store)
    store.set_relationship_status(rel.relationship_id, "rejected", evidence_ids=(uuid4(),), reason="serial conflict")
    store.set_relationship_status(rel.relationship_id, "possible", evidence_ids=(uuid4(),), reason="review with new evidence")
    assert store.get_relationship(rel.relationship_id).status == "possible"


def test_reject_missing_evidence_for_decision():
    store = DeviceDiscoveryStore()
    _, _, rel = pair(store)
    with pytest.raises(ValueError, match="supporting evidence"):
        store.set_relationship_status(rel.relationship_id, "confirmed", evidence_ids=(), reason="accepted")
    assert store.get_relationship(rel.relationship_id).status == "possible"
    assert not store.decisions


def test_reject_duplicate_evidence_for_decision():
    store = DeviceDiscoveryStore()
    candidate = registered(store)
    eid = uuid4()
    with pytest.raises(ValueError, match="Duplicate evidence"):
        store.resolve_candidate(candidate.candidate_id, uuid4(), evidence_ids=(eid, eid), reason="serial")
    assert store.get_candidate(candidate.candidate_id).resolved_device_id is None


def test_resolve_candidate_and_reverse_without_losing_history():
    store = DeviceDiscoveryStore()
    original = registered(store)
    device_id = uuid4()
    store.resolve_candidate(original.candidate_id, device_id, evidence_ids=(uuid4(),), reason="trusted serial")
    assert store.candidates_for_device(device_id)[0].candidate_id == original.candidate_id
    assert store.get_candidate(original.candidate_id).status == "resolved"
    assert original.status == "candidate"
    store.unresolve_candidate(original.candidate_id, evidence_ids=(uuid4(),), reason="incorrect identity")
    assert store.candidates_for_device(device_id) == ()
    assert store.get_candidate(original.candidate_id).status == "candidate"
    assert [decision.new_value for decision in store.decisions_for(original.candidate_id)] == [str(device_id), "unresolved"]


def test_multiple_candidates_can_resolve_to_one_canonical_device():
    store = DeviceDiscoveryStore()
    a, b = registered(store), registered(store)
    device_id = uuid4()
    for candidate in (a, b):
        store.resolve_candidate(candidate.candidate_id, device_id, evidence_ids=(uuid4(),), reason="verified same chassis")
    assert {c.candidate_id for c in store.candidates_for_device(device_id)} == {a.candidate_id, b.candidate_id}


def test_cannot_silently_reassign_resolved_candidate():
    store = DeviceDiscoveryStore()
    a = registered(store)
    store.resolve_candidate(a.candidate_id, uuid4(), evidence_ids=(uuid4(),), reason="first")
    with pytest.raises(ValueError, match="reverse first"):
        store.resolve_candidate(a.candidate_id, uuid4(), evidence_ids=(uuid4(),), reason="second")


def test_inactive_candidate_cannot_be_resolved():
    store = DeviceDiscoveryStore()
    a = registered(store)
    store.set_candidate_status(a.candidate_id, "rejected", evidence_ids=(uuid4(),), reason="invalid")
    with pytest.raises(ValueError, match="Inactive"):
        store.resolve_candidate(a.candidate_id, uuid4(), evidence_ids=(uuid4(),), reason="invalid")


def test_same_status_transition_is_idempotent():
    store = DeviceDiscoveryStore()
    _, _, rel = pair(store)
    store.set_relationship_status(rel.relationship_id, "possible", evidence_ids=(), reason=None)
    assert store.decisions == ()
