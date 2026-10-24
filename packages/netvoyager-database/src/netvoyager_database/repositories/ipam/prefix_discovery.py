
"""SQL persistence for prefix discovery; transactions are caller-owned."""

from __future__ import annotations

from ipaddress import ip_network
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
)
from netvoyager_network.ipam.discovery.decisions import (
    PrefixDiscoveryDecision,
)

from netvoyager_database.entities.ipam import (
    PrefixObservationEntity,
    PrefixDiscoveryCandidateEntity,
    PrefixCandidateObservationEntity,
    PrefixDiscoveryRelationshipEntity,
    PrefixDiscoveryDecisionEntity,
)
from netvoyager_database.entities.ipam.canonical import NetworkPrefixEntity

from netvoyager_database.mappers.ipam.prefix_discovery import (
    observation_to_domain,
    observation_to_entity,
    candidate_to_domain,
    candidate_to_entity,
    relationship_to_domain,
    relationship_to_entity,
    decision_to_domain,
    decision_to_entity,
)
from netvoyager_database.exceptions import (
    RepositoryConflictError,
    RepositoryNotFoundError,
)


class SqlPrefixDiscoveryRepository:
    """Persist already-decided discovery changes without commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _flush(self, code: str, message: str) -> None:
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code=code,
                message=message,
            ) from exc

    def add_observation(
        self,
        observation: PrefixObservation,
        dataset_id: UUID,
        *,
        source_name: str | None = None,
        source_method: str | None = None,
    ) -> None:
        """Persist an observation and its source profile context."""
        if (source_name is None) != (source_method is None):
            raise ValueError(
                "Source name and method must be provided together"
            )

        if source_name is not None:
            if (
                not isinstance(source_name, str)
                or not isinstance(source_method, str)
                or not source_name.strip()
                or not source_method.strip()
            ):
                raise ValueError("Source identifiers cannot be empty")

        entity = observation_to_entity(observation, dataset_id)
        entity.source_name = source_name
        entity.source_method = source_method

        self._session.add(entity)
        self._flush(
            "storage.prefix_observation_conflict",
            "Cannot insert prefix observation.",
        )

    def get_observation(
        self,
        observation_id: UUID,
    ) -> PrefixObservation | None:
        entity = self._session.get(
            PrefixObservationEntity,
            observation_id,
        )

        return (
            observation_to_domain(entity)
            if entity is not None
            else None
        )

    def get_observation_source(
        self,
        observation_id: UUID,
    ) -> tuple[str, str] | None:
        """Read the source identity recorded during observation ingestion."""
        entity = self._session.get(
            PrefixObservationEntity,
            observation_id,
        )

        if entity is None:
            return None

        if entity.source_name is None or entity.source_method is None:
            return None

        return entity.source_name, entity.source_method

    def get_candidate(
        self,
        candidate_id: UUID,
    ) -> PrefixDiscoveryCandidate | None:
        entity = self._session.get(
            PrefixDiscoveryCandidateEntity,
            candidate_id,
        )

        return (
            candidate_to_domain(entity)
            if entity is not None
            else None
        )

    def find_candidates(
        self,
        prefix: str,
        address_space_id: UUID | None = None,
    ) -> tuple[PrefixDiscoveryCandidate, ...]:
        """Find candidates using the indexed normalized CIDR."""
        normalized = ip_network(
            prefix,
            strict=False,
        ).with_prefixlen

        query = select(PrefixDiscoveryCandidateEntity).where(
            PrefixDiscoveryCandidateEntity.prefix == normalized
        )

        if address_space_id is not None:
            query = query.where(
                PrefixDiscoveryCandidateEntity.address_space_id
                == address_space_id
            )

        entities = self._session.scalars(
            query.order_by(
                PrefixDiscoveryCandidateEntity.candidate_id
            )
        ).all()

        return tuple(
            candidate_to_domain(entity)
            for entity in entities
        )

    def _validate_resolved_prefix(
        self,
        candidate: PrefixDiscoveryCandidate,
    ) -> None:
        """Verify that resolved candidates reference compatible prefixes."""
        if candidate.resolved_prefix_id is None:
            return

        canonical = self._session.get(
            NetworkPrefixEntity,
            candidate.resolved_prefix_id,
        )

        if canonical is None:
            raise RepositoryConflictError(
                code="storage.canonical_prefix_not_found",
                message="Resolved canonical prefix does not exist.",
            )

        if candidate.prefix is None:
            raise RepositoryConflictError(
                code="storage.candidate_prefix_missing",
                message="Resolved candidate must have a CIDR.",
            )

        if candidate.prefix.with_prefixlen != canonical.prefix:
            raise RepositoryConflictError(
                code="storage.canonical_prefix_mismatch",
                message="Candidate and canonical prefix CIDRs differ.",
            )

        if (
            candidate.address_space_id is not None
            and candidate.address_space_id != canonical.address_space_id
        ):
            raise RepositoryConflictError(
                code="storage.address_space_mismatch",
                message="Candidate and canonical AddressSpaces differ.",
            )

    def add_candidate(
        self,
        candidate: PrefixDiscoveryCandidate,
    ) -> None:
        self._validate_resolved_prefix(candidate)

        self._session.add(candidate_to_entity(candidate))
        self._flush(
            "storage.prefix_candidate_conflict",
            "Cannot insert prefix discovery candidate.",
        )

    def save_candidate(
        self,
        candidate: PrefixDiscoveryCandidate,
    ) -> None:
        self._validate_resolved_prefix(candidate)

        entity = self._session.get(
            PrefixDiscoveryCandidateEntity,
            candidate.candidate_id,
        )

        if entity is None:
            raise RepositoryNotFoundError(
                code="storage.prefix_candidate_not_found",
                message="Prefix discovery candidate does not exist.",
            )

        mapped = candidate_to_entity(candidate)

        for attribute in (
            "status",
            "prefix",
            "address_space_id",
            "first_seen",
            "last_seen",
            "resolved_prefix_id",
        ):
            setattr(
                entity,
                attribute,
                getattr(mapped, attribute),
            )

        self._flush(
            "storage.prefix_candidate_update_conflict",
            "Cannot update prefix discovery candidate.",
        )

    def link_observation(
        self,
        observation_id: UUID,
        candidate_id: UUID,
    ) -> None:
        """Create an idempotent observation association."""
        key = (observation_id, candidate_id)

        if self._session.get(
            PrefixCandidateObservationEntity,
            key,
        ) is not None:
            return

        self._session.add(
            PrefixCandidateObservationEntity(
                observation_id=observation_id,
                candidate_id=candidate_id,
            )
        )

        self._flush(
            "storage.prefix_observation_link_conflict",
            "Cannot link prefix observation and candidate.",
        )

    def candidate_observation_ids(
        self,
        candidate_id: UUID,
    ) -> tuple[UUID, ...]:
        query = (
            select(PrefixCandidateObservationEntity.observation_id)
            .where(
                PrefixCandidateObservationEntity.candidate_id
                == candidate_id
            )
            .order_by(
                PrefixCandidateObservationEntity.observation_id
            )
        )

        return tuple(self._session.scalars(query).all())

    def get_relationship(
        self,
        relationship_id: UUID,
    ) -> PrefixDiscoveryCandidateRelationship | None:
        entity = self._session.get(
            PrefixDiscoveryRelationshipEntity,
            relationship_id,
        )

        return (
            relationship_to_domain(entity)
            if entity is not None
            else None
        )

    def find_relationship(
        self,
        candidate_a_id: UUID,
        candidate_b_id: UUID,
    ) -> PrefixDiscoveryCandidateRelationship | None:
        if candidate_a_id == candidate_b_id:
            return None

        first, second = sorted(
            (candidate_a_id, candidate_b_id)
        )

        entity = self._session.scalar(
            select(PrefixDiscoveryRelationshipEntity).where(
                PrefixDiscoveryRelationshipEntity.candidate_a_id
                == first,
                PrefixDiscoveryRelationshipEntity.candidate_b_id
                == second,
            )
        )

        return (
            relationship_to_domain(entity)
            if entity is not None
            else None
        )

    def relationships_for_candidate(
        self,
        candidate_id: UUID,
    ) -> tuple[PrefixDiscoveryCandidateRelationship, ...]:
        query = (
            select(PrefixDiscoveryRelationshipEntity)
            .where(
                or_(
                    PrefixDiscoveryRelationshipEntity.candidate_a_id
                    == candidate_id,
                    PrefixDiscoveryRelationshipEntity.candidate_b_id
                    == candidate_id,
                )
            )
            .order_by(
                PrefixDiscoveryRelationshipEntity.relationship_id
            )
        )

        return tuple(
            relationship_to_domain(entity)
            for entity in self._session.scalars(query).all()
        )

    def add_relationship(
        self,
        relationship: PrefixDiscoveryCandidateRelationship,
    ) -> None:
        self._session.add(
            relationship_to_entity(relationship)
        )
        self._flush(
            "storage.prefix_relationship_conflict",
            "Cannot insert prefix discovery relationship.",
        )

    def save_relationship(
        self,
        relationship: PrefixDiscoveryCandidateRelationship,
    ) -> None:
        entity = self._session.get(
            PrefixDiscoveryRelationshipEntity,
            relationship.relationship_id,
        )

        if entity is None:
            raise RepositoryNotFoundError(
                code="storage.prefix_relationship_not_found",
                message="Prefix relationship does not exist.",
            )

        mapped = relationship_to_entity(relationship)

        if (
            entity.candidate_a_id,
            entity.candidate_b_id,
        ) != (
            mapped.candidate_a_id,
            mapped.candidate_b_id,
        ):
            raise RepositoryConflictError(
                code="storage.prefix_relationship_identity_conflict",
                message="Relationship endpoints are immutable.",
            )

        entity.status = mapped.status
        entity.evidence_ids = mapped.evidence_ids

        self._flush(
            "storage.prefix_relationship_update_conflict",
            "Cannot update prefix discovery relationship.",
        )

    def candidates_for_prefix(
        self,
        prefix_id: UUID,
    ) -> tuple[PrefixDiscoveryCandidate, ...]:
        query = (
            select(PrefixDiscoveryCandidateEntity)
            .where(
                PrefixDiscoveryCandidateEntity.resolved_prefix_id
                == prefix_id
            )
            .order_by(
                PrefixDiscoveryCandidateEntity.candidate_id
            )
        )

        return tuple(
            candidate_to_domain(entity)
            for entity in self._session.scalars(query).all()
        )

    def append_decision(
        self,
        decision: PrefixDiscoveryDecision,
    ) -> None:
        self._session.add(decision_to_entity(decision))
        self._flush(
            "storage.prefix_decision_conflict",
            "Cannot append prefix discovery decision.",
        )

    def decisions_for(
        self,
        subject_id: UUID,
    ) -> tuple[PrefixDiscoveryDecision, ...]:
        query = (
            select(PrefixDiscoveryDecisionEntity)
            .where(
                PrefixDiscoveryDecisionEntity.subject_id == subject_id
            )
            .order_by(
                PrefixDiscoveryDecisionEntity.timestamp,
                PrefixDiscoveryDecisionEntity.decision_id,
            )
        )

        return tuple(
            decision_to_domain(entity)
            for entity in self._session.scalars(query).all()
        )
