
"""Policy-authorized reconciliation of prefix discovery candidates.

Reconciliation derives source authority from persisted observations.
The service never commits database transactions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.protocols.unit_of_work import UnitOfWorkProtocol

from netvoyager_network.ipam.discovery.decisions import (
    PrefixDiscoveryDecision,
)
from netvoyager_network.ipam.models import NetworkPrefix


class PrefixReconciliationService:
    """Resolve discovery candidates using administrator-defined policies."""

    def __init__(
        self,
        uow: UnitOfWorkProtocol,
        policy_engine: PolicyEngine,
    ) -> None:
        self._uow = uow
        self._policies = policy_engine

    def reconcile(
        self,
        *,
        candidate_id: UUID,
        observation_id: UUID,
        actor_type: Literal["human", "system", "ai_agent"],
        actor_id: str,
        requirements: Mapping[str, bool] | None = None,
        evidence_ids: tuple[UUID, ...] = (),
    ) -> NetworkPrefix:
        """Resolve a candidate to an existing or new canonical prefix.

        Authority comes from the observation's persisted source profile.

        A fully trusted source bypasses secondary requirements.
        Conditionally trusted sources must satisfy configured conditions.

        All persistence belongs to the caller-owned Unit of Work.
        """
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")

        if not isinstance(observation_id, UUID):
            raise TypeError("observation_id must be a UUID")

        if actor_type not in {"human", "system", "ai_agent"}:
            raise ValueError("Invalid actor_type")

        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("actor_id must be nonempty")

        discovery = self._uow.prefix_discovery
        canonical_repository = self._uow.network_prefixes

        observation = discovery.get_observation(observation_id)

        if observation is None:
            raise ValueError("Prefix observation does not exist")

        candidate = discovery.get_candidate(candidate_id)

        if candidate is None:
            raise ValueError("Prefix discovery candidate does not exist")

        linked_observations = discovery.candidate_observation_ids(
            candidate_id
        )

        if observation_id not in linked_observations:
            raise ValueError(
                "Observation is not associated with the candidate"
            )

        source_context = discovery.get_observation_source(
            observation_id
        )

        if source_context is None:
            raise PermissionError(
                "Observation has no registered source context"
            )

        source_name, source_method = source_context

        if candidate.status in {"rejected", "retired"}:
            raise ValueError(
                "Rejected or retired candidates cannot be reconciled"
            )

        if candidate.prefix is None:
            raise ValueError("Candidate has no CIDR")

        if candidate.prefix != observation.prefix:
            raise ValueError(
                "Observation and candidate CIDRs do not match"
            )

        observed_space = observation.address_space_id
        candidate_space = candidate.address_space_id

        if (
            observed_space is not None
            and candidate_space is not None
            and observed_space != candidate_space
        ):
            raise ValueError(
                "Observation and candidate AddressSpaces conflict"
            )

        address_space_id = (
            observed_space
            if observed_space is not None
            else candidate_space
        )

        if address_space_id is None:
            raise ValueError(
                "Canonical reconciliation requires an established "
                "AddressSpace"
            )

        expected = NetworkPrefix(
            prefix=observation.prefix,
            address_space_id=address_space_id,
        )

        existing = canonical_repository.find_prefix(
            expected.prefix.with_prefixlen,
            expected.address_space_id,
        )

        if existing is not None and existing.id != expected.id:
            raise ValueError(
                "Existing canonical prefix identity is inconsistent"
            )

        if candidate.status == "resolved":
            if candidate.resolved_prefix_id != expected.id:
                raise ValueError(
                    "Candidate already resolves to another prefix"
                )

            canonical = canonical_repository.get_prefix(expected.id)

            if canonical is None:
                raise ValueError(
                    "Resolved canonical prefix does not exist"
                )

            return canonical

        actions = (
            ("promote_candidate",)
            if existing is not None
            else (
                "create_canonical_prefix",
                "promote_candidate",
            )
        )

        policy_version: int | None = None

        for action in actions:
            result = self._policies.evaluate(
                source_name,
                source_method,
                claim="prefix.existence",
                action=action,
                requirements=requirements,
            )

            if not result.allowed:
                raise PermissionError(
                    f"Source policy denied {action}: {result.reason}"
                )

            policy_version = result.policy_version

        if existing is None:
            space = canonical_repository.get_address_space(
                address_space_id
            )

            if space is None:
                raise ValueError(
                    "AddressSpace must exist before canonical creation"
                )

            canonical_repository.add_prefix(expected)
            canonical = expected
        else:
            canonical = existing

        updated = replace(
            candidate,
            status="resolved",
            address_space_id=address_space_id,
            resolved_prefix_id=canonical.id,
        )

        discovery.save_candidate(updated)

        decision = PrefixDiscoveryDecision(
            decision_type="candidate_resolution",
            subject_id=candidate.candidate_id,
            subject_type="candidate",
            previous_value=(
                str(candidate.resolved_prefix_id)
                if candidate.resolved_prefix_id is not None
                else None
            ),
            new_value=str(canonical.id),
            evidence_ids=evidence_ids,
            reason="Policy-authorized canonical prefix reconciliation",
            timestamp=datetime.now(timezone.utc),
            source_id=source_name,
            method=source_method,
            policy_version=policy_version,
            actor_type=actor_type,
            actor_id=actor_id,
        )

        discovery.append_decision(decision)

        return canonical
