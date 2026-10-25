
"""SQLAlchemy repository for physical-device discovery persistence.

Candidates and relationships are immutable domain snapshots.
The repository stores current snapshots and append-only decision history.

Identity reconciliation, policy evaluation, and authorization belong
outside the database layer.

Transactions are owned by the Unit of Work.
"""

from __future__ import annotations

from ipaddress import IPv4Address
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from netvoyager_core.logging import get_logger
from netvoyager_database.entities.devices.discovery_candidate import (
    DeviceDiscoveryCandidateEntity,
)
from netvoyager_database.entities.devices.discovery_decision import (
    DeviceDiscoveryDecisionEntity,
)
from netvoyager_database.entities.devices.discovery_relationship import (
    DeviceDiscoveryRelationshipEntity,
)
from netvoyager_database.exceptions import (
    RepositoryConflictError,
    RepositoryNotFoundError,
)
from netvoyager_database.mappers.devices.discovery_candidate import (
    candidate_to_domain,
    candidate_to_entity,
)
from netvoyager_database.mappers.devices.discovery_decision import (
    decision_to_domain,
    decision_to_entity,
)
from netvoyager_database.mappers.devices.discovery_relationship import (
    relationship_to_domain,
    relationship_to_entity,
)
from netvoyager_network.device.discovery.decisions import (
    DeviceDiscoveryDecision,
)
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.discovery.relationships import (
    DeviceDiscoveryCandidateRelationship,
)


logger = get_logger(__name__)


class SqlDeviceDiscoveryRepository:
    """Persist discovery candidates, relationships, and audit decisions.

    Uses a caller-owned SQLAlchemy Session. Write operations flush but
    never commit or roll back the surrounding transaction.

    State transitions must already be authorized by the calling service.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the repository with an active database session."""
        self._session = session

    def get_candidate(
        self,
        candidate_id: UUID,
    ) -> DeviceDiscoveryCandidate | None:
        """Retrieve an existing candidate by UUID."""
        entity = self._session.get(
            DeviceDiscoveryCandidateEntity,
            candidate_id,
        )
        return candidate_to_domain(entity) if entity is not None else None

    def find_by_serial(
        self,
        serial_number: str,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Find candidates using their exact stored serial number."""
        statement = select(DeviceDiscoveryCandidateEntity).where(
            DeviceDiscoveryCandidateEntity.serial_number == serial_number
        )
        return self._find_candidates(statement)

    def find_by_management_ip(
        self,
        management_ip: IPv4Address,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Find candidates using an exact management IPv4 address."""
        statement = select(DeviceDiscoveryCandidateEntity).where(
            DeviceDiscoveryCandidateEntity.management_ip == str(management_ip)
        )
        return self._find_candidates(statement)

    def find_by_name(
        self,
        name: str,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Find candidates using an exact observed name."""
        statement = select(DeviceDiscoveryCandidateEntity).where(
            DeviceDiscoveryCandidateEntity.name == name
        )
        return self._find_candidates(statement)

    def add_candidate(
        self,
        candidate: DeviceDiscoveryCandidate,
    ) -> None:
        """Insert a new candidate without replacing existing identity."""
        self._session.add(candidate_to_entity(candidate))
        self._flush(
            code="storage.discovery_candidate_conflict",
            message="Cannot insert a conflicting discovery candidate.",
            details={"candidate_id": str(candidate.candidate_id)},
        )

        logger.debug(
            "Discovery candidate inserted",
            extra={"candidate_id": str(candidate.candidate_id)},
        )

    def save_candidate(
        self,
        candidate: DeviceDiscoveryCandidate,
    ) -> None:
        """Persist an already-reconciled discovery candidate snapshot.

        The calling Analysis service is responsible for determining
        permitted attribute updates and recording attribute conflicts.

        This repository performs no reconciliation or policy decisions.
        """
        entity = self._session.get(
            DeviceDiscoveryCandidateEntity,
            candidate.candidate_id,
        )

        if entity is None:
            raise RepositoryNotFoundError(
                code="storage.discovery_candidate_not_found",
                message="Cannot update a discovery candidate that does not exist.",
                details={"candidate_id": str(candidate.candidate_id)},
            )

        updated = candidate_to_entity(candidate)

        # Discovery identity and lifecycle
        entity.status = updated.status
        entity.name = updated.name
        entity.host_name = updated.host_name
        entity.serial_number = updated.serial_number
        entity.management_ip = updated.management_ip

        # Reported inventory attributes
        entity.site = updated.site
        entity.role = updated.role
        entity.primary_ipv4 = updated.primary_ipv4
        entity.manufacturer = updated.manufacturer
        entity.model = updated.model
        entity.software_version = updated.software_version
        entity.asset_tag = updated.asset_tag

        # Discovery timestamps and canonical resolution
        entity.first_seen = updated.first_seen
        entity.last_seen = updated.last_seen
        entity.resolved_device_id = updated.resolved_device_id

        self._flush(
            code="storage.discovery_candidate_update_conflict",
            message="Cannot persist the discovery candidate state.",
            details={"candidate_id": str(candidate.candidate_id)},
        )

        logger.debug(
            "Discovery candidate state persisted",
            extra={"candidate_id": str(candidate.candidate_id)},
        )

    def get_relationship(
        self,
        relationship_id: UUID,
    ) -> DeviceDiscoveryCandidateRelationship | None:
        """Return a candidate relationship by UUID."""
        entity = self._session.get(
            DeviceDiscoveryRelationshipEntity,
            relationship_id,
        )
        return relationship_to_domain(entity) if entity is not None else None

    def find_relationship(
        self,
        candidate_a_id: UUID,
        candidate_b_id: UUID,
    ) -> DeviceDiscoveryCandidateRelationship | None:
        """Find a candidate relationship regardless of input order."""
        if candidate_a_id == candidate_b_id:
            return None

        first, second = sorted((candidate_a_id, candidate_b_id))

        statement = select(DeviceDiscoveryRelationshipEntity).where(
            DeviceDiscoveryRelationshipEntity.candidate_a_id == first,
            DeviceDiscoveryRelationshipEntity.candidate_b_id == second,
        )

        entity = self._session.scalar(statement)
        return relationship_to_domain(entity) if entity is not None else None

    def relationships_for_candidate(
        self,
        candidate_id: UUID,
    ) -> tuple[DeviceDiscoveryCandidateRelationship, ...]:
        """Return every relationship involving the candidate."""
        statement = (
            select(DeviceDiscoveryRelationshipEntity)
            .where(
                or_(
                    DeviceDiscoveryRelationshipEntity.candidate_a_id
                    == candidate_id,
                    DeviceDiscoveryRelationshipEntity.candidate_b_id
                    == candidate_id,
                )
            )
            .order_by(DeviceDiscoveryRelationshipEntity.relationship_id)
        )
        entities = self._session.scalars(statement).all()
        return tuple(relationship_to_domain(entity) for entity in entities)

    def add_relationship(
        self,
        relationship: DeviceDiscoveryCandidateRelationship,
    ) -> None:
        """Insert a new relationship between existing candidates."""
        self._session.add(relationship_to_entity(relationship))

        self._flush(
            code="storage.discovery_relationship_conflict",
            message="Cannot insert a conflicting discovery relationship.",
            details={
                "relationship_id": str(relationship.relationship_id),
            },
        )

        logger.debug(
            "Discovery relationship inserted",
            extra={"relationship_id": str(relationship.relationship_id)},
        )

    def save_relationship(
        self,
        relationship: DeviceDiscoveryCandidateRelationship,
    ) -> None:
        """Update status and evidence on an existing relationship."""
        entity = self._session.get(
            DeviceDiscoveryRelationshipEntity,
            relationship.relationship_id,
        )
        if entity is None:
            raise RepositoryNotFoundError(
                code="storage.discovery_relationship_not_found",
                message="Cannot update a discovery relationship that does not exist.",
                details={
                    "relationship_id": str(relationship.relationship_id),
                },
            )

        updated = relationship_to_entity(relationship)

        if (
            entity.candidate_a_id != updated.candidate_a_id
            or entity.candidate_b_id != updated.candidate_b_id
        ):
            raise RepositoryConflictError(
                code="storage.discovery_relationship_identity_conflict",
                message="Stored relationship endpoints do not match.",
                details={
                    "relationship_id": str(relationship.relationship_id),
                },
            )

        entity.status = updated.status
        entity.evidence_ids = updated.evidence_ids

        self._flush(
            code="storage.discovery_relationship_update_conflict",
            message="Cannot persist the discovery relationship state.",
            details={
                "relationship_id": str(relationship.relationship_id),
            },
        )

        logger.debug(
            "Discovery relationship state persisted",
            extra={"relationship_id": str(relationship.relationship_id)},
        )

    def candidates_for_device(
        self,
        device_id: UUID,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return candidates resolved to the given canonical device."""
        statement = select(DeviceDiscoveryCandidateEntity).where(
            DeviceDiscoveryCandidateEntity.resolved_device_id == device_id
        )
        return self._find_candidates(statement)

    def save_resolution(
        self,
        candidate: DeviceDiscoveryCandidate,
    ) -> None:
        """Persist an already-authorized candidate resolution snapshot."""
        self.save_candidate(candidate)

    def decisions_for(
        self,
        subject_id: UUID,
    ) -> tuple[DeviceDiscoveryDecision, ...]:
        """Return all decision records for a discovery subject."""
        statement = (
            select(DeviceDiscoveryDecisionEntity)
            .where(DeviceDiscoveryDecisionEntity.subject_id == subject_id)
            .order_by(
                DeviceDiscoveryDecisionEntity.timestamp,
                DeviceDiscoveryDecisionEntity.decision_id,
            )
        )
        entities = self._session.scalars(statement).all()
        return tuple(decision_to_domain(entity) for entity in entities)

    def append_decision(
        self,
        decision: DeviceDiscoveryDecision,
    ) -> None:
        """Append a discovery decision without modifying previous records."""
        entity = decision_to_entity(decision)
        self._session.add(entity)

        self._flush(
            code="storage.discovery_decision_conflict",
            message="Cannot append the discovery decision.",
            details={
                "subject_id": str(decision.subject_id),
                "decision_type": decision.decision_type,
            },
        )

        logger.debug(
            "Discovery decision appended",
            extra={
                "subject_id": str(decision.subject_id),
                "decision_type": decision.decision_type,
                "actor_type": decision.actor_type,
                "actor_id": decision.actor_id,
            },
        )

    def _find_candidates(
        self,
        statement,
    ) -> tuple[DeviceDiscoveryCandidate, ...]:
        """Return candidates with deterministic UUID ordering."""
        statement = statement.order_by(
            DeviceDiscoveryCandidateEntity.candidate_id
        )
        entities = self._session.scalars(statement).all()
        return tuple(candidate_to_domain(entity) for entity in entities)

    def _flush(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, object],
    ) -> None:
        """Flush changes and translate database integrity conflicts."""
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise RepositoryConflictError(
                code=code,
                message=message,
                details=details,
            ) from exc
