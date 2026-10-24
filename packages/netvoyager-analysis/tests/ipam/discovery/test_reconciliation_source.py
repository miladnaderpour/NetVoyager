
"""Integration tests for source-authorized prefix reconciliation."""

from ipaddress import ip_network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.discovery.assignment import (
    PrefixObservationAssignmentService,
)
from netvoyager_analysis.ipam.discovery.reconciliation import (
    PrefixReconciliationService,
)
from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.policies.models import (
    ClaimActionPolicy,
    ClaimPolicy,
    SourceProfile,
    SourceTrustPolicy,
)
from netvoyager_analysis.sources.models import Source

from netvoyager_database.engine import create_database_engine
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)

from netvoyager_network.ipam.address_space import GLOBAL_ADDRESS_SPACE
from netvoyager_network.ipam.models import NetworkPrefix


@pytest.fixture
def uow_factory():
    """Provide isolated SQLite transactions."""
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)

    try:
        yield lambda: NetworkInventoryUnitOfWork(factory)
    finally:
        engine.dispose()


@pytest.fixture
def policies():
    """Register synthetic authoritative and conditional sources."""
    engine = PolicyEngine()

    engine.register(
        SourceTrustPolicy(
            profile=SourceProfile(
                source_id="trusted_test",
                method="api",
            ),
            version=1,
            fully_trusted=True,
        )
    )

    engine.register(
        SourceTrustPolicy(
            profile=SourceProfile(
                source_id="conditional_test",
                method="api",
            ),
            version=1,
            claims=(
                ClaimPolicy(
                    claim="prefix.existence",
                    authority="trusted",
                    actions=(
                        ClaimActionPolicy(
                            action="create_canonical_prefix",
                            requirements=("verified_reporting_source",),
                        ),
                        ClaimActionPolicy(
                            action="promote_candidate",
                            requirements=("verified_reporting_source",),
                        ),
                    ),
                ),
            ),
        )
    )

    return engine


def prepare(
    uow_factory,
    *,
    source_name="trusted_test",
    address_space_id=None,
    with_source=True,
    create_space=True,
):
    """Persist an observation, candidate and optional source context."""
    if address_space_id is None:
        address_space_id = GLOBAL_ADDRESS_SPACE.id

    source = Source(
        name=source_name,
        source_type="api",
    )

    observation = PrefixObservation(
        local_ref="synthetic-prefix",
        prefix=ip_network("192.0.2.0/24"),
        observation_kind="inventory",
        address_space_id=address_space_id,
    )

    with uow_factory() as uow:
        if create_space:
            uow.network_prefixes.add_address_space(
                GLOBAL_ADDRESS_SPACE
            )

        plan = PrefixObservationAssignmentService(uow).assign(
            observation,
            dataset_id=uuid4(),
            source=source if with_source else None,
        )
        uow.commit()

    return observation.observation_id, plan.candidate.candidate_id


def reconcile(uow, policies, observation_id, candidate_id, **kwargs):
    """Invoke reconciliation through its public ID-based interface."""
    return PrefixReconciliationService(uow, policies).reconcile(
        candidate_id=candidate_id,
        observation_id=observation_id,
        actor_type="system",
        actor_id="synthetic-reconciler",
        **kwargs,
    )


def test_fully_trusted_source_creates_canonical(
    uow_factory,
    policies,
):
    observation_id, candidate_id = prepare(uow_factory)

    with uow_factory() as uow:
        prefix = reconcile(
            uow, policies, observation_id, candidate_id
        )
        uow.commit()

    with uow_factory() as uow:
        candidate = uow.prefix_discovery.get_candidate(candidate_id)

        assert candidate is not None
        assert candidate.status == "resolved"
        assert candidate.resolved_prefix_id == prefix.id
        assert uow.network_prefixes.get_prefix(prefix.id) == prefix

        decisions = uow.prefix_discovery.decisions_for(candidate_id)

        assert len(decisions) == 1
        assert decisions[0].decision_type == "candidate_resolution"
        assert decisions[0].source_id == "trusted_test"
        assert decisions[0].policy_version == 1


def test_existing_canonical_prefix_is_reused(
    uow_factory,
    policies,
):
    observation_id, candidate_id = prepare(uow_factory)

    canonical = NetworkPrefix(
        prefix=ip_network("192.0.2.0/24"),
        address_space_id=GLOBAL_ADDRESS_SPACE.id,
    )

    with uow_factory() as uow:
        uow.network_prefixes.add_prefix(canonical)
        uow.commit()

    with uow_factory() as uow:
        result = reconcile(
            uow, policies, observation_id, candidate_id
        )
        uow.commit()

    assert result.id == canonical.id

    with uow_factory() as uow:
        candidate = uow.prefix_discovery.get_candidate(candidate_id)
        assert candidate.resolved_prefix_id == canonical.id


def test_unknown_source_is_denied(uow_factory, policies):
    observation_id, candidate_id = prepare(
        uow_factory,
        source_name="unknown_test",
    )

    with uow_factory() as uow:
        with pytest.raises(PermissionError):
            reconcile(
                uow, policies, observation_id, candidate_id
            )

    with uow_factory() as uow:
        candidate = uow.prefix_discovery.get_candidate(candidate_id)
        assert candidate.status == "candidate"


def test_observation_without_source_cannot_authorize(
    uow_factory,
    policies,
):
    observation_id, candidate_id = prepare(
        uow_factory,
        with_source=False,
    )

    with uow_factory() as uow:
        with pytest.raises(
            PermissionError,
            match="no registered source context",
        ):
            reconcile(
                uow, policies, observation_id, candidate_id
            )


def test_conditional_source_requires_validation(
    uow_factory,
    policies,
):
    observation_id, candidate_id = prepare(
        uow_factory,
        source_name="conditional_test",
    )

    with uow_factory() as uow:
        with pytest.raises(PermissionError):
            reconcile(
                uow, policies, observation_id, candidate_id
            )

    with uow_factory() as uow:
        prefix = reconcile(
            uow,
            policies,
            observation_id,
            candidate_id,
            requirements={"verified_reporting_source": True},
        )
        uow.commit()

    assert prefix.prefix == ip_network("192.0.2.0/24")


def test_reconciliation_is_idempotent(
    uow_factory,
    policies,
):
    observation_id, candidate_id = prepare(uow_factory)

    with uow_factory() as uow:
        first = reconcile(
            uow, policies, observation_id, candidate_id
        )
        uow.commit()

    with uow_factory() as uow:
        second = reconcile(
            uow, policies, observation_id, candidate_id
        )

        assert second.id == first.id
        assert len(
            uow.prefix_discovery.decisions_for(candidate_id)
        ) == 1


def test_reconciliation_rolls_back(
    uow_factory,
    policies,
):
    observation_id, candidate_id = prepare(uow_factory)

    with uow_factory() as uow:
        prefix = reconcile(
            uow, policies, observation_id, candidate_id
        )
        # No commit.

    with uow_factory() as uow:
        assert uow.network_prefixes.get_prefix(prefix.id) is None

        candidate = uow.prefix_discovery.get_candidate(candidate_id)

        assert candidate.status == "candidate"
        assert candidate.resolved_prefix_id is None
        assert uow.prefix_discovery.decisions_for(candidate_id) == ()


def test_reconciliation_rejects_unlinked_observation(
    uow_factory,
    policies,
):
    first_observation_id, first_candidate_id = prepare(uow_factory)

    with uow_factory() as uow:
        another = PrefixObservation(
            local_ref="another-prefix",
            prefix=ip_network("198.51.100.0/24"),
            observation_kind="inventory",
            address_space_id=GLOBAL_ADDRESS_SPACE.id,
        )

        uow.prefix_discovery.add_observation(
            another,
            uuid4(),
            source_name="trusted_test",
            source_method="api",
        )
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(
            ValueError,
            match="not associated",
        ):
            reconcile(
                uow,
                policies,
                another.observation_id,
                first_candidate_id,
            )


def test_source_context_cannot_change_on_replay(
    uow_factory,
):
    observation_id, _ = prepare(uow_factory)

    with uow_factory() as uow:
        observation = uow.prefix_discovery.get_observation(
            observation_id
        )

        with pytest.raises(
            ValueError,
            match="Conflicting source context",
        ):
            PrefixObservationAssignmentService(uow).assign(
                observation,
                dataset_id=uuid4(),
                source=Source(
                    name="another_source",
                    source_type="api",
                ),
            )
