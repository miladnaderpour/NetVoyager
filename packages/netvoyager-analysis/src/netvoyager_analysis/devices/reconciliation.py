
"""Policy-controlled physical-device reconciliation.

The Device Analysis processor determines unambiguous identity matches.
This module authorizes and applies canonical creation and candidate
resolution using existing Unit of Work repositories.

No legacy DeviceDiscoveryStore or service class is required.

The caller owns transaction commit and rollback.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from netvoyager_core.exceptions import NetVoyagerError
from netvoyager_core.logging import get_logger
from netvoyager_network.device.discovery.decisions import (
    DeviceDiscoveryDecision,
)
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.models import NetworkDevice

from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.protocols.unit_of_work import (
    UnitOfWorkProtocol,
)


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DeviceReconciliationResult:
    """Result of an authorized canonical reconciliation attempt."""

    device: NetworkDevice | None
    created: bool
    resolved_candidate_ids: tuple[UUID, ...]
    changed: bool


def _fail(
    code: str,
    message: str,
    **details: object,
) -> None:
    """Raise a structured reconciliation failure."""
    raise NetVoyagerError(
        code=code,
        message=message,
        details=details,
    )


def _serial_equivalent(
    left: str | None,
    right: str | None,
) -> bool:
    """Accept exact serials or differences limited to leading zeros."""
    if not left or not right:
        return False

    a = left.strip()
    b = right.strip()

    if not a or not b:
        return False

    if a.casefold() == b.casefold():
        return True

    if not (
        a.isascii()
        and b.isascii()
        and a.isdecimal()
        and b.isdecimal()
    ):
        return False

    normalized_a = a.lstrip("0")
    normalized_b = b.lstrip("0")

    return bool(normalized_a) and normalized_a == normalized_b


def reconcile(
    *,
    candidate: DeviceDiscoveryCandidate,
    canonical: NetworkDevice | None,
    canonical_name: str | None,
    source: SourceRef,
    policies: PolicyEngine,
    uow: UnitOfWorkProtocol,
    evidence_ids: tuple[UUID, ...] = (),
    actor_type: Literal["human", "system", "ai_agent"],
    actor_id: str,
    reason: str = "Authorized physical device reconciliation",
    dry_run: bool = False,
) -> DeviceReconciliationResult:
    """Create/reuse a canonical device and resolve one candidate.

    The caller must have established that canonical matching is
    unambiguous. This function validates serial correspondence,
    source authority, resolution consistency, and audit metadata.

    No transaction is committed here.

    Reconciliation is idempotent for an already resolved candidate.
    """
    if not isinstance(actor_id, str) or not actor_id.strip():
        _fail(
            "analysis.device_missing_actor",
            "Reconciliation requires an identified actor.",
        )

    if candidate.status in {"rejected", "retired"}:
        _fail(
            "analysis.device_candidate_inactive",
            "An inactive candidate cannot be reconciled.",
            candidate_id=str(candidate.candidate_id),
        )

    if not candidate.serial_number or not candidate.serial_number.strip():
        _fail(
            "analysis.device_missing_serial",
            "Canonical reconciliation requires a physical serial.",
            candidate_id=str(candidate.candidate_id),
        )

    if len(evidence_ids) != len(set(evidence_ids)):
        _fail(
            "analysis.device_duplicate_evidence",
            "Duplicate evidence references are not permitted.",
            candidate_id=str(candidate.candidate_id),
        )

    # Ensure the supplied candidate is the current persisted identity.
    stored = uow.discovery.get_candidate(candidate.candidate_id)

    if stored is None:
        _fail(
            "analysis.device_candidate_not_found",
            "The discovery candidate does not exist.",
            candidate_id=str(candidate.candidate_id),
        )

    if stored != candidate:
        _fail(
            "analysis.device_candidate_state_conflict",
            "Candidate state has changed since it was read.",
            candidate_id=str(candidate.candidate_id),
        )

    if canonical is None:
        created = True

    if created:
        name = (canonical_name or candidate.name or "").strip()

        if not name:
            _fail(
                "analysis.device_missing_canonical_name",
                "Canonical creation requires a device name.",
                candidate_id=str(candidate.candidate_id),
            )

        existing_name = uow.devices.find_by_name(name)

        if existing_name is not None:
            _fail(
                "analysis.device_canonical_name_conflict",
                "Canonical name is already assigned.",
                canonical_name=name,
            )

        device = NetworkDevice(
            name=name,
            serial_number=candidate.serial_number,
        )
    else:
        device = canonical

        persisted_device = uow.devices.get_by_id(device.device_id)

        if persisted_device is None:
            _fail(
                "analysis.device_canonical_not_found",
                "Matched canonical device is not persisted.",
                device_id=str(device.device_id),
            )

        if not _serial_equivalent(
            candidate.serial_number,
            persisted_device.serial_number,
        ):
            _fail(
                "analysis.device_serial_conflict",
                "Candidate and canonical serial identities conflict.",
                candidate_id=str(candidate.candidate_id),
                device_id=str(device.device_id),
            )

        device = persisted_device

    if (
        candidate.resolved_device_id is not None
        and candidate.resolved_device_id != device.device_id
    ):
        _fail(
            "analysis.device_resolution_conflict",
            "Candidate is already resolved to another canonical device.",
            candidate_id=str(candidate.candidate_id),
            existing_device_id=str(candidate.resolved_device_id),
            proposed_device_id=str(device.device_id),
        )

    if candidate.status == "resolved":
        return DeviceReconciliationResult(
            device=device,
            created=False,
            resolved_candidate_ids=(),
            changed=False,
        )

    # A rejected relationship must not connect two candidates
    # resolved to the same canonical device.
    for relationship in uow.discovery.relationships_for_candidate(
        candidate.candidate_id
    ):
        if relationship.status != "rejected":
            continue

        other_id = (
            relationship.candidate_b_id
            if relationship.candidate_a_id == candidate.candidate_id
            else relationship.candidate_a_id
        )

        other = uow.discovery.get_candidate(other_id)

        if (
            other is not None
            and other.resolved_device_id == device.device_id
        ):
            _fail(
                "analysis.device_rejected_relationship",
                "Rejected candidate relationship blocks resolution.",
                candidate_id=str(candidate.candidate_id),
                other_candidate_id=str(other_id),
            )

    requirements = {
        "unique_physical_serial": True,
        "unambiguous_device_match": True,
        "verified_device_identity": True,
    }

    # Creation and candidate promotion are separate policy actions.
    if created:
        create_permission = policies.evaluate(
            source.source_id,
            source.method,
            claim="device.physical_identity",
            action="create_canonical_device",
            requirements=requirements,
        )

        if not create_permission.allowed:
            _fail(
                "analysis.device_canonical_creation_denied",
                "Source policy denied canonical device creation.",
                source_id=source.source_id,
                source_method=source.method,
                reason=create_permission.reason,
            )

    promotion_permission = policies.evaluate(
        source.source_id,
        source.method,
        claim="device.physical_identity",
        action="promote_candidate",
        requirements=requirements,
    )

    if not promotion_permission.allowed:
        _fail(
            "analysis.device_candidate_promotion_denied",
            "Source policy denied candidate resolution.",
            source_id=source.source_id,
            source_method=source.method,
            reason=promotion_permission.reason,
        )

    updated_candidate = replace(
        candidate,
        status="resolved",
        resolved_device_id=device.device_id,
    )

    decision = DeviceDiscoveryDecision(
        decision_type="candidate_resolution",
        subject_type="candidate",
        subject_id=candidate.candidate_id,
        previous_value=(
            str(candidate.resolved_device_id)
            if candidate.resolved_device_id is not None
            else None
        ),
        new_value=str(device.device_id),
        evidence_ids=evidence_ids,
        reason=reason,
        timestamp=datetime.now(timezone.utc),
        source_id=source.source_id,
        method=source.method,
        policy_version=promotion_permission.policy_version,
        actor_type=actor_type,
        actor_id=actor_id,
    )

    if not dry_run:
        if created:
            uow.devices.add(device)

        uow.discovery.save_resolution(updated_candidate)
        uow.discovery.append_decision(decision)

    logger.info(
        "Device reconciliation evaluated",
        extra={
            "candidate_id": str(candidate.candidate_id),
            "device_id": str(device.device_id),
            "created": created,
            "dry_run": dry_run,
            "source_id": source.source_id,
        },
    )

    return DeviceReconciliationResult(
        device=device,
        created=created,
        resolved_candidate_ids=(candidate.candidate_id,),
        changed=True,
    )
