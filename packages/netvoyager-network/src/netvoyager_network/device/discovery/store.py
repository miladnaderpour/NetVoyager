"""Controlled discovery candidate relationships, resolution, and decisions.

This store is an operational registry, not an evidence database or matcher.
It preserves candidate IDs and immutable snapshots with auditable changes.
Policy evaluation and identity validation are performed before callers
invoke its decision methods.
"""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Literal, TypeAlias
from uuid import UUID

from .models import DeviceDiscoveryCandidate, DeviceDiscoveryCandidateStatus
from .relationships import (
    DeviceDiscoveryCandidateRelationship,
    DeviceDiscoveryRelationshipStatus,
)


DeviceDiscoveryDecisionType: TypeAlias = Literal[
    "relationship_status", "candidate_resolution", "candidate_lifecycle",
    "candidate_attributes",
]


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DeviceDiscoveryDecision:
    """An append-only description of an approved discovery change.

    Evidence IDs are references, never the source of matching attributes.
    The calling reconciliation layer is responsible for validating evidence
    and policy authorization; this store does not certify either.
    """

    decision_type: DeviceDiscoveryDecisionType
    subject_id: UUID
    previous_value: str | None
    new_value: str
    evidence_ids: tuple[UUID, ...]
    reason: str | None
    timestamp: datetime
    source_id: str | None = None
    method: str | None = None
    policy_version: int | None = None


class DeviceDiscoveryStore:
    """Manage discovery candidates through indexed, auditable operations."""

    def __init__(self) -> None:
        self._candidates: dict[UUID, DeviceDiscoveryCandidate] = {}
        self._relationships: dict[
            UUID, DeviceDiscoveryCandidateRelationship
        ] = {}
        self._candidate_relationships: dict[UUID, set[UUID]] = defaultdict(set)
        self._device_candidates: dict[UUID, set[UUID]] = defaultdict(set)
        self._decisions: list[DeviceDiscoveryDecision] = []

    @staticmethod
    def _evidence(evidence_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        """Require supporting references for a recorded decision."""
        if not evidence_ids:
            raise ValueError("Decision requires supporting evidence IDs")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Duplicate evidence IDs are not allowed")
        return evidence_ids

    def _record(
        self,
        decision_type: DeviceDiscoveryDecisionType,
        subject_id: UUID,
        previous_value: str | None,
        new_value: str,
        *,
        evidence_ids: tuple[UUID, ...],
        reason: str | None,
        source_id: str | None = None,
        method: str | None = None,
        policy_version: int | None = None,
    ) -> None:
        """Append a decision after the corresponding operation succeeds."""
        self._decisions.append(DeviceDiscoveryDecision(
            decision_type=decision_type,
            subject_id=subject_id,
            previous_value=previous_value,
            new_value=new_value,
            evidence_ids=evidence_ids,
            reason=reason,
            timestamp=_utc_now(),
            source_id=source_id,
            method=method,
            policy_version=policy_version,
        ))

    def add_candidate(self, candidate: DeviceDiscoveryCandidate) -> None:
        """Register a new unresolved candidate only."""
        if candidate.candidate_id in self._candidates:
            raise ValueError(f"Candidate already exists: {candidate.candidate_id}")
        if candidate.status != "candidate" or candidate.resolved_device_id is not None:
            raise ValueError("New candidates must begin unresolved")
        self._candidates[candidate.candidate_id] = candidate

    def get_candidate(self, candidate_id: UUID) -> DeviceDiscoveryCandidate:
        """Get the immutable current candidate snapshot."""
        return self._candidates[candidate_id]

    def find_candidate(self, candidate_id: UUID) -> DeviceDiscoveryCandidate | None:
        """Get a candidate or None."""
        return self._candidates.get(candidate_id)

    def update_candidate_attributes(
        self,
        candidate_id: UUID,
        *,
        evidence_ids: tuple[UUID, ...],
        reason: str,
        name: str | None = None,
        host_name: str | None = None,
        serial_number: str | None = None,
        management_ip: IPv4Address | None = None,
    ) -> DeviceDiscoveryCandidate:
        """Update provided non-None summary fields with a recorded decision.

        Clearing a field is intentionally not supported in this first version.
        Attribute-claim history is maintained by AttributeAssertionStore.
        """
        candidate = self.get_candidate(candidate_id)
        self._evidence(evidence_ids)
        if candidate.status in {"rejected", "retired"}:
            raise ValueError("Inactive candidates cannot be updated")
        changes = {
            key: value for key, value in {
                "name": name, "host_name": host_name,
                "serial_number": serial_number, "management_ip": management_ip,
            }.items() if value is not None and getattr(candidate, key) != value
        }
        if not changes:
            return candidate
        updated = replace(candidate, **changes, last_seen=_utc_now())
        self._candidates[candidate_id] = updated
        self._record(
            "candidate_attributes", candidate_id,
            ",".join(f"{key}={getattr(candidate, key)}" for key in changes),
            ",".join(f"{key}={value}" for key, value in changes.items()),
            evidence_ids=evidence_ids, reason=reason,
        )
        return updated

    def set_candidate_status(
        self,
        candidate_id: UUID,
        status: DeviceDiscoveryCandidateStatus,
        *,
        evidence_ids: tuple[UUID, ...],
        reason: str,
    ) -> DeviceDiscoveryCandidate:
        """Change an unresolved candidate's lifecycle with an audit trail."""
        candidate = self.get_candidate(candidate_id)
        if status not in {"candidate", "corroborated", "rejected", "retired"}:
            raise ValueError("Resolution must use resolve_candidate")
        if candidate.resolved_device_id is not None:
            raise ValueError("Reverse resolution before changing lifecycle")
        if status == candidate.status:
            return candidate
        self._evidence(evidence_ids)
        if not reason.strip():
            raise ValueError("Lifecycle changes require a reason")
        updated = replace(candidate, status=status)
        self._candidates[candidate_id] = updated
        self._record(
            "candidate_lifecycle", candidate_id, candidate.status, status,
            evidence_ids=evidence_ids, reason=reason,
        )
        return updated

    def add_relationship(
        self, relationship: DeviceDiscoveryCandidateRelationship,
    ) -> None:
        """Register a possible relationship, never a pre-confirmed one."""
        rid = relationship.relationship_id
        if rid in self._relationships:
            raise ValueError(f"Relationship already exists: {rid}")
        if relationship.status != "possible":
            raise ValueError("New relationships must start as possible")
        for candidate_id in (
            relationship.candidate_a_id, relationship.candidate_b_id,
        ):
            if candidate_id not in self._candidates:
                raise KeyError(f"Unknown candidate: {candidate_id}")
        self._relationships[rid] = relationship
        self._candidate_relationships[relationship.candidate_a_id].add(rid)
        self._candidate_relationships[relationship.candidate_b_id].add(rid)

    def get_relationship(
        self, relationship_id: UUID,
    ) -> DeviceDiscoveryCandidateRelationship:
        """Return the immutable relationship snapshot."""
        return self._relationships[relationship_id]

    def find_relationship(
        self, candidate_a_id: UUID, candidate_b_id: UUID,
    ) -> DeviceDiscoveryCandidateRelationship | None:
        """Find a relationship independent of candidate order."""
        if candidate_a_id == candidate_b_id:
            return None
        key = DeviceDiscoveryCandidateRelationship(
            candidate_a_id, candidate_b_id,
        ).relationship_id
        return self._relationships.get(key)

    def relationships_for_candidate(
        self, candidate_id: UUID,
    ) -> tuple[DeviceDiscoveryCandidateRelationship, ...]:
        """Return relationships in registration order."""
        self.get_candidate(candidate_id)
        keys = self._candidate_relationships.get(candidate_id, set())
        return tuple(
            rel for rid, rel in self._relationships.items() if rid in keys
        )

    def set_relationship_status(
        self,
        relationship_id: UUID,
        status: DeviceDiscoveryRelationshipStatus,
        *,
        evidence_ids: tuple[UUID, ...],
        reason: str | None = None,
        source_id: str | None = None,
        method: str | None = None,
        policy_version: int | None = None,
    ) -> None:
        """Record a reversible, evidence-backed relationship transition."""
        relationship = self.get_relationship(relationship_id)
        if status not in {"possible", "confirmed", "rejected"}:
            raise ValueError(f"Invalid relationship status: {status}")
        if status == relationship.status:
            return
        self._evidence(evidence_ids)
        if not reason or not reason.strip():
            raise ValueError("Relationship changes require a reason")
        updated = replace(
            relationship, status=status,
            evidence_ids=relationship.evidence_ids.union(evidence_ids),
        )
        self._relationships[relationship_id] = updated
        self._record(
            "relationship_status", relationship_id,
            relationship.status, status,
            evidence_ids=evidence_ids, reason=reason,
            source_id=source_id, method=method, policy_version=policy_version,
        )

    def resolve_candidate(
        self,
        candidate_id: UUID,
        device_id: UUID,
        *,
        evidence_ids: tuple[UUID, ...],
        reason: str | None = None,
        source_id: str | None = None,
        method: str | None = None,
        policy_version: int | None = None,
    ) -> None:
        """Resolve a candidate to a canonical ID after external validation."""
        candidate = self.get_candidate(candidate_id)
        if candidate.resolved_device_id == device_id:
            return
        if candidate.resolved_device_id is not None:
            raise ValueError("Candidate already resolved; reverse first")
        if candidate.status in {"rejected", "retired"}:
            raise ValueError("Inactive candidates cannot be resolved")
        self._evidence(evidence_ids)
        if not reason or not reason.strip():
            raise ValueError("Resolution requires a reason")
        updated = replace(candidate, status="resolved", resolved_device_id=device_id)
        self._candidates[candidate_id] = updated
        self._device_candidates[device_id].add(candidate_id)
        self._record(
            "candidate_resolution", candidate_id, None, str(device_id),
            evidence_ids=evidence_ids, reason=reason,
            source_id=source_id, method=method, policy_version=policy_version,
        )

    def unresolve_candidate(
        self,
        candidate_id: UUID,
        *,
        evidence_ids: tuple[UUID, ...],
        reason: str,
    ) -> None:
        """Reverse a prior resolution, retaining its original decision."""
        candidate = self.get_candidate(candidate_id)
        old_id = candidate.resolved_device_id
        if old_id is None:
            raise ValueError("Candidate is not resolved")
        self._evidence(evidence_ids)
        if not reason.strip():
            raise ValueError("Reversal requires a reason")
        updated = replace(candidate, status="candidate", resolved_device_id=None)
        self._candidates[candidate_id] = updated
        self._device_candidates[old_id].discard(candidate_id)
        if not self._device_candidates[old_id]:
            del self._device_candidates[old_id]
        self._record(
            "candidate_resolution", candidate_id, str(old_id), "unresolved",
            evidence_ids=evidence_ids, reason=reason,
        )

    def candidates_for_device(
        self, device_id: UUID,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return current candidates resolved to a canonical device."""
        ids = self._device_candidates.get(device_id, set())
        return tuple(
            candidate for cid, candidate in self._candidates.items() if cid in ids
        )

    def decisions_for(self, subject_id: UUID) -> tuple[DeviceDiscoveryDecision, ...]:
        """Return the append-only history for a candidate or relationship."""
        return tuple(
            decision for decision in self._decisions
            if decision.subject_id == subject_id
        )

    @property
    def candidates(self) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return current candidate snapshots in registration order."""
        return tuple(self._candidates.values())

    @property
    def relationships(self) -> tuple[DeviceDiscoveryCandidateRelationship, ...]:
        """Return current relationship snapshots in registration order."""
        return tuple(self._relationships.values())

    @property
    def decisions(self) -> tuple[DeviceDiscoveryDecision, ...]:
        """Return decision history in append order."""
        return tuple(self._decisions)
