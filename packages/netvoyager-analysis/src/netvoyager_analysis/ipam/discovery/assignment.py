
"""Apply prefix assignment plans within a caller-owned Unit of Work."""

from __future__ import annotations

from uuid import UUID

from netvoyager_analysis.ipam.discovery.planning import (
    PrefixObservationAssignmentPlan,
    plan_prefix_observation_assignment,
)
from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_analysis.protocols.unit_of_work import UnitOfWorkProtocol


class PrefixObservationAssignmentService:
    """Persist assignment decisions without owning transaction boundaries."""

    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    def assign(
        self,
        observation: PrefixObservation,
        *,
        dataset_id: UUID,
    ) -> PrefixObservationAssignmentPlan:
        """Assign one observation to one provisional candidate.

        Replays preserve the existing observation-to-candidate link.
        The caller must commit the surrounding Unit of Work.
        """
        if not isinstance(observation, PrefixObservation):
            raise TypeError("observation must be a PrefixObservation")
        if not isinstance(dataset_id, UUID):
            raise TypeError("dataset_id must be a UUID")

        repository = self._uow.prefix_discovery
        existing = repository.get_observation(observation.observation_id)

        if existing is not None and existing != observation:
            raise ValueError("Conflicting observation data for observation_id")

        candidates = repository.find_candidates(
            observation.prefix.with_prefixlen
        )

        if existing is not None:
            linked = [
                candidate
                for candidate in candidates
                if observation.observation_id
                in repository.candidate_observation_ids(
                    candidate.candidate_id
                )
            ]

            if len(linked) > 1:
                raise ValueError(
                    "Observation has multiple candidate assignments"
                )

            if linked:
                return PrefixObservationAssignmentPlan(
                    observation_id=observation.observation_id,
                    action="reuse_candidate",
                    candidate=linked[0],
                )

        plan = plan_prefix_observation_assignment(
            observation,
            candidates,
        )

        if existing is None:
            repository.add_observation(observation, dataset_id)

        if plan.action == "create_candidate":
            repository.add_candidate(plan.candidate)

        repository.link_observation(
            observation.observation_id,
            plan.candidate.candidate_id,
        )

        return plan
