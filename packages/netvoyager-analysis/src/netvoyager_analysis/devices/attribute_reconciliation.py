"""Reconcile observed hostnames as policy-controlled attribute assertions.

Physical identity resolution is independent of attribute acceptance. This
service does not mutate NetworkDevice or use evidence as a matching index.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from netvoyager_network.device.models import NetworkDevice

from ..attributes.models import AttributeAssertion
from ..attributes.store import AttributeAssertionStore
from .identity_validation import IdentityValidationResult
from .matching_rules import SourceRef

if TYPE_CHECKING:
    from ..policies.engine import PolicyEngine


AttributeReconciliationStatus = Literal[
    "confirmed", "proposed", "conflict", "unchanged", "denied"
]


@dataclass(frozen=True, slots=True)
class AttributeReconciliationResult:
    """Result of evaluating one observed canonical-device hostname."""

    status: AttributeReconciliationStatus
    device_id: UUID
    assertion_id: UUID | None
    reason: str


class DeviceAttributeReconciliationService:
    """Record and authorize claims without overwriting canonical attributes."""

    def __init__(
        self,
        *,
        assertion_store: AttributeAssertionStore,
        policy_engine: "PolicyEngine",
    ) -> None:
        self._assertions = assertion_store
        self._policies = policy_engine

    def reconcile_host_name(
        self,
        device: NetworkDevice,
        observed_host_name: str | None,
        *,
        source: SourceRef,
        evidence_ids: tuple[UUID, ...],
        identity: IdentityValidationResult,
    ) -> AttributeReconciliationResult:
        """Record a hostname assertion and confirm it when allowed.

        An existing different hostname, or a different confirmed assertion,
        is a conflict requiring an explicit acceptance decision elsewhere.
        Even confirmed assertions do not update the canonical device here.
        """
        if not evidence_ids or len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Unique supporting evidence IDs are required")

        value = observed_host_name.strip() if observed_host_name else ""
        if not value:
            return AttributeReconciliationResult(
                "unchanged", device.device_id, None, "No observed hostname"
            )

        if not identity.verified or not identity.unambiguous_device_match:
            return AttributeReconciliationResult(
                "denied", device.device_id, None, "Physical identity is not verified"
            )

        existing = self._assertions.find_value(
            "network_device", device.device_id, "host_name", value
        )
        assertions = self._assertions.for_field(
            "network_device", device.device_id, "host_name"
        )
        conflicting_confirmed = any(
            assertion.status == "confirmed" and assertion.value.casefold() != value.casefold()
            for assertion in assertions
            if isinstance(assertion.value, str)
        )
        conflicting_canonical = bool(
            device.host_name and device.host_name.strip().casefold() != value.casefold()
        )

        # Evaluate the real policy before creating or transitioning claims.
        policy = self._policies.evaluate(
            source.source_id,
            source.method,
            claim="device.host_name",
            action="confirm_attribute",
            requirements={
                "verified_device_identity": identity.verified,
                "unique_physical_serial": identity.unique_physical_serial,
                "unambiguous_device_match": identity.unambiguous_device_match,
            },
        )

        # A newly observed value is retained even if it cannot be confirmed.
        if existing is None:
            existing = AttributeAssertion(
                target_type="network_device",
                target_id=device.device_id,
                field_name="host_name",
                value=value,
                evidence_ids=evidence_ids,
            )
            self._assertions.add(existing)
        else:
            for evidence_id in evidence_ids:
                existing = self._assertions.add_evidence(existing.assertion_id, evidence_id)

        if conflicting_canonical or conflicting_confirmed:
            return AttributeReconciliationResult(
                "conflict", device.device_id, existing.assertion_id,
                "Hostname differs from canonical or confirmed value; no overwrite",
            )

        if existing.status == "confirmed":
            return AttributeReconciliationResult(
                "unchanged", device.device_id, existing.assertion_id,
                "Hostname assertion already confirmed",
            )

        if not policy.allowed:
            return AttributeReconciliationResult(
                "proposed", device.device_id, existing.assertion_id,
                f"Confirmation not authorized: {policy.reason}",
            )

        if existing.status == "superseded":
            return AttributeReconciliationResult(
                "proposed", device.device_id, existing.assertion_id,
                "Superseded assertion cannot be reconfirmed",
            )

        confirmed = self._assertions.transition(
            existing.assertion_id,
            "confirmed",
            evidence_ids=evidence_ids,
            source_id=source.source_id,
            method=source.method,
            policy_version=policy.policy_version,
            reason="Verified physical identity and authorized hostname assertion",
            policy_result=policy,
        )
        return AttributeReconciliationResult(
            "confirmed", device.device_id, confirmed.assertion_id,
            "Attribute assertion confirmed; canonical value unchanged",
        )
