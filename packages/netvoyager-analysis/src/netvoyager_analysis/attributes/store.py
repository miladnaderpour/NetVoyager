
"""Store evidence-backed attribute assertions and validation decisions.

The assertion store maintains provisional and confirmed attribute claims,
supporting evidence references, and append-only decision history.

Policy authorization is supplied by PolicyEngine. Canonical device
updates and conflict reconciliation are managed separately.
"""

from dataclasses import replace
from uuid import UUID

from ..protocols.evidence import EvidenceRepositoryProtocol
from ..policies.models import PolicyEvaluationResult
from .models import (
    AttributeAssertion,
    AttributeAssertionDecision,
    AttributeAssertionStatus,
    AttributeTargetType,
    AttributeValue,
)


class AttributeAssertionStore:
    """Manage attribute assertions with controlled state transitions.

    Assertions are indexed by identity and target. Registered assertions
    are immutable; updates replace stored snapshots rather than modifying
    objects returned to callers.

    Evidence records remain in the Evidence repository. Decisions preserve the
    validation history without modifying original observations.
    """

    def __init__(
        self,
        *,
        evidence_store: EvidenceRepositoryProtocol,
    ) -> None:
        self._evidence_store = evidence_store

        self._assertions: dict[
            UUID, AttributeAssertion
        ] = {}

        self._target_assertions: dict[
            tuple[AttributeTargetType, UUID],
            set[UUID],
        ] = {}

        self._decisions: list[AttributeAssertionDecision] = []

    def add(
        self,
        assertion: AttributeAssertion,
    ) -> None:
        """Register a proposed assertion with existing evidence.

        Reject duplicate identities and logically duplicate claims.
        Confirmation and other status changes must use transition().
        """
        if assertion.assertion_id in self._assertions:
            raise ValueError(
                f"Attribute assertion already exists: "
                f"{assertion.assertion_id}"
            )

        if assertion.status != "proposed":
            raise ValueError(
                "New assertions must have proposed status"
            )

        self._validate_evidence(assertion.evidence_ids)

        for existing in self.for_field(
            assertion.target_type,
            assertion.target_id,
            assertion.field_name,
        ):
            if (
                type(existing.value) is type(assertion.value)
                and existing.value == assertion.value
            ):
                raise ValueError(
                    "An assertion for this target, field, "
                    "and value already exists"
                )

        self._assertions[assertion.assertion_id] = assertion

        key = (
            assertion.target_type,
            assertion.target_id,
        )

        self._target_assertions.setdefault(
            key,
            set(),
        ).add(assertion.assertion_id)

        for evidence_id in assertion.evidence_ids:
            self._evidence_store.link(
                evidence_id,
                "attribute_assertion",
                assertion.assertion_id,
            )

    def get(
        self,
        assertion_id: UUID,
    ) -> AttributeAssertion:
        """Return an assertion by UUID, raising KeyError if absent."""
        return self._assertions[assertion_id]

    def find(
        self,
        assertion_id: UUID,
    ) -> AttributeAssertion | None:
        """Return an assertion by UUID or None when absent."""
        return self._assertions.get(assertion_id)

    def for_target(
        self,
        target_type: AttributeTargetType,
        target_id: UUID,
    ) -> tuple[AttributeAssertion, ...]:
        """Return assertions for a candidate or canonical device."""
        key = (target_type, target_id)

        assertion_ids = self._target_assertions.get(
            key,
            set(),
        )

        return tuple(
            assertion
            for assertion_id, assertion in self._assertions.items()
            if assertion_id in assertion_ids
        )

    def for_field(
        self,
        target_type: AttributeTargetType,
        target_id: UUID,
        field_name: str,
    ) -> tuple[AttributeAssertion, ...]:
        """Return all asserted values for one target attribute."""
        return tuple(
            assertion
            for assertion in self.for_target(
                target_type,
                target_id,
            )
            if assertion.field_name == field_name
        )

    def find_value(
        self,
        target_type: AttributeTargetType,
        target_id: UUID,
        field_name: str,
        value: AttributeValue,
    ) -> AttributeAssertion | None:
        """Find an existing assertion with the exact value and type."""
        for assertion in self.for_field(
            target_type,
            target_id,
            field_name,
        ):
            if (
                type(assertion.value) is type(value)
                and assertion.value == value
            ):
                return assertion

        return None

    def add_evidence(
        self,
        assertion_id: UUID,
        evidence_id: UUID,
    ) -> AttributeAssertion:
        """Add supporting evidence without changing validation status.

        Repeated evidence references have no effect. Original evidence
        records and existing assertion decisions remain unchanged.
        """
        assertion = self.get(assertion_id)

        self._validate_evidence((evidence_id,))

        if evidence_id in assertion.evidence_ids:
            return assertion

        updated = replace(
            assertion,
            evidence_ids=(
                *assertion.evidence_ids,
                evidence_id,
            ),
        )

        self._evidence_store.link(
            evidence_id,
            "attribute_assertion",
            assertion_id,
        )

        self._assertions[assertion_id] = updated

        return updated

    def transition(
        self,
        assertion_id: UUID,
        status: AttributeAssertionStatus,
        *,
        evidence_ids: tuple[UUID, ...],
        source_id: str,
        method: str,
        policy_version: int,
        reason: str | None = None,
        policy_result: PolicyEvaluationResult | None = None,
    ) -> AttributeAssertion:
        """Apply an auditable assertion status transition.

        Confirmation requires an allowed PolicyEngine result for the
        matching device attribute and confirm_attribute action.

        Disputes and supersession require an explanation. Domain-specific
        rules governing competing claims belong to reconciliation.
        """
        assertion = self.get(assertion_id)

        allowed_transitions: dict[
            AttributeAssertionStatus,
            frozenset[AttributeAssertionStatus],
        ] = {
            "proposed": frozenset({
                "confirmed",
                "disputed",
                "superseded",
            }),
            "confirmed": frozenset({
                "disputed",
                "superseded",
            }),
            "disputed": frozenset({
                "confirmed",
                "superseded",
            }),
            "superseded": frozenset(),
        }

        if status not in allowed_transitions[assertion.status]:
            raise ValueError(
                f"Invalid attribute transition: "
                f"{assertion.status} -> {status}"
            )

        if not evidence_ids:
            raise ValueError(
                "Attribute decisions require supporting evidence"
            )

        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(
                "Duplicate decision evidence IDs are not allowed"
            )

        self._validate_evidence(evidence_ids)

        if not source_id.strip() or not method.strip():
            raise ValueError(
                "Attribute decisions require a source and method"
            )

        if policy_version < 1:
            raise ValueError(
                "Policy version must be positive"
            )

        if status in {"disputed", "superseded"}:
            if not reason or not reason.strip():
                raise ValueError(
                    "Dispute and supersession require a reason"
                )

        if status == "confirmed":
            if policy_result is None or not policy_result.allowed:
                raise ValueError(
                    "Attribute confirmation requires policy authorization"
                )

            if (
                policy_result.claim
                != f"device.{assertion.field_name}"
                or policy_result.action != "confirm_attribute"
                or policy_result.source_id != source_id
                or policy_result.method != method
                or policy_result.policy_version != policy_version
            ):
                raise ValueError(
                    "Policy result does not match the attribute decision"
                )

        combined_evidence = assertion.evidence_ids + tuple(
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in assertion.evidence_ids
        )

        updated = replace(
            assertion,
            status=status,
            evidence_ids=combined_evidence,
        )

        decision = AttributeAssertionDecision(
            assertion_id=assertion_id,
            previous_status=assertion.status,
            new_status=status,
            evidence_ids=evidence_ids,
            source_id=source_id,
            method=method,
            policy_version=policy_version,
            reason=reason,
        )

        for evidence_id in evidence_ids:
            self._evidence_store.link(
                evidence_id,
                "attribute_assertion",
                assertion_id,
            )

        self._assertions[assertion_id] = updated
        self._decisions.append(decision)

        return updated

    def decisions_for(
        self,
        assertion_id: UUID,
    ) -> tuple[AttributeAssertionDecision, ...]:
        """Return recorded decisions for an existing assertion."""
        self.get(assertion_id)

        return tuple(
            decision
            for decision in self._decisions
            if decision.assertion_id == assertion_id
        )

    def _validate_evidence(
        self,
        evidence_ids: tuple[UUID, ...],
    ) -> None:
        """Ensure every referenced evidence record exists."""
        for evidence_id in evidence_ids:
            if self._evidence_store.get(evidence_id) is None:
                raise KeyError(evidence_id)

    @property
    def assertions(self) -> tuple[AttributeAssertion, ...]:
        """Return all registered assertions in insertion order."""
        return tuple(self._assertions.values())

    @property
    def decisions(self) -> tuple[AttributeAssertionDecision, ...]:
        """Return all decisions in insertion order."""
        return tuple(self._decisions)
