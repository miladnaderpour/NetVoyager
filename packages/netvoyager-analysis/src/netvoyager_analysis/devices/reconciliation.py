"""Authorize and apply physical-device identity reconciliation.

The caller supplies trusted source context, supporting evidence IDs, a
complete canonical inventory, and PolicyEngine. This service does not
inspect EvidenceStore or treat matching evidence as the identity database.
"""
from __future__ import annotations
from collections.abc import MutableMapping
from typing import TYPE_CHECKING
from dataclasses import dataclass
from uuid import UUID

from netvoyager_network.device.models import NetworkDevice
if TYPE_CHECKING:
    from ..policies.engine import PolicyEngine
from .candidate_matching import IdentityTarget, compare_identity_targets
from .matching_rules import SourceRef
from netvoyager_network.device.discovery.store import DeviceDiscoveryStore
from .identity_validation import IdentityValidator

@dataclass(frozen=True, slots=True)
class DeviceReconciliationResult:
    device: NetworkDevice
    created: bool
    resolved_candidate_ids: tuple[UUID, ...]

class DeviceReconciliationService:
    """Resolve trusted physical identities without implicit candidate merging."""

    def __init__(self, *, discovery_store: DeviceDiscoveryStore,
                 policy_engine: PolicyEngine,
                 validator: IdentityValidator | None = None) -> None:
        self._discovery_store = discovery_store
        self._policy_engine = policy_engine
        self._validator = validator or IdentityValidator()

    def reconcile(
        self,
        observed: IdentityTarget,
        *,
        canonical_devices: MutableMapping[UUID, NetworkDevice],
        evidence_ids: tuple[UUID, ...],
        candidate_sources: dict[UUID, SourceRef] | None = None,
        name: str | None = None,
        reason: str = "Trusted physical identity reconciliation",
    ) -> DeviceReconciliationResult:
        """Create/reuse a canonical identity and resolve strongly matching candidates.

        The canonical mapping and discovery store must be maintained by one
        orchestrator. Callers must pass trusted, complete canonical inventory.
        A new canonical name must be unambiguous under the name-based UUIDv5
        contract. Policy evaluation is required before ANY mutation.
        """
        if observed.source is None:
            raise ValueError("Explicit source and collection method required")
        if not evidence_ids:
            raise ValueError("Resolution requires supporting evidence references")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Duplicate supporting evidence IDs")
        outcome = self._validator.validate_canonical_identity(
            observed, canonical_devices=canonical_devices.values(),
        )
        if not outcome.verified:
            raise ValueError(outcome.reason)
        source = observed.source
        authorization = self._policy_engine.evaluate(
            source.source_id, source.method,
            claim="device.physical_identity",
            action="create_canonical_device" if outcome.matched_device_id is None else "promote_candidate",
            requirements={
                "unique_physical_serial": outcome.unique_physical_serial,
                "unambiguous_device_match": outcome.unambiguous_device_match,
                "verified_device_identity": outcome.verified,
            },
        )
        if not authorization.allowed:
            raise PermissionError(authorization.reason)
        if outcome.matched_device_id is None:
            if not name or not name.strip():
                raise ValueError("Canonical device name required for new device")
            # UUIDv5 is name-based, so never reuse a name for a new physical identity.
            new_device = NetworkDevice(name=name.strip(), serial_number=observed.device.serial_number)
            if new_device.device_id in canonical_devices:
                raise ValueError("Canonical device name already assigned to another identity")
            device = new_device
            created = True
        else:
            device = canonical_devices[outcome.matched_device_id]
            created = False

        # Stage all resolutions and reject contradictions before modifying stores.
        candidates = self._discovery_store.candidates
        pairs: list[UUID] = []
        for candidate in candidates:
            if candidate.status in {"rejected", "retired"}:
                continue
            candidate_source = (candidate_sources or {}).get(candidate.candidate_id)
            if candidate_source is not None and not isinstance(candidate_source, SourceRef):
                raise TypeError("candidate_sources values must be SourceRef")
            match = compare_identity_targets(
                observed, IdentityTarget(candidate, candidate_source),
            )
            if match is None or not self._validator.validate_match(match).verified:
                continue
            if candidate.resolved_device_id not in {None, device.device_id}:
                raise ValueError("Candidate already resolved to a conflicting device")
            for relationship in self._discovery_store.relationships_for_candidate(candidate.candidate_id):
                if relationship.status != "rejected":
                    continue
                other_id = (relationship.candidate_b_id
                            if relationship.candidate_a_id == candidate.candidate_id
                            else relationship.candidate_a_id)
                other = self._discovery_store.get_candidate(other_id)
                if other.resolved_device_id == device.device_id or other_id in pairs:
                    raise ValueError("Rejected candidate relationship blocks resolution")
            if candidate.resolved_device_id is None:
                pairs.append(candidate.candidate_id)

        if pairs:
            candidate_policy = self._policy_engine.evaluate(
                source.source_id, source.method,
                claim="device.physical_identity", action="promote_candidate",
                requirements={
                    "unique_physical_serial": outcome.unique_physical_serial,
                    "unambiguous_device_match": outcome.unambiguous_device_match,
                    "verified_device_identity": outcome.verified,
                },
            )
            if not candidate_policy.allowed:
                raise PermissionError(candidate_policy.reason)

        if created:
            canonical_devices[device.device_id] = device
        for cid in pairs:
            self._discovery_store.resolve_candidate(
                cid, device.device_id, evidence_ids=evidence_ids,
                reason=reason, source_id=source.source_id,
                method=source.method,
                policy_version=authorization.policy_version,
            )
        return DeviceReconciliationResult(device, created, tuple(pairs))
