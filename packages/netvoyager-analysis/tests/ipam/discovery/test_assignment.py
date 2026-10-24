
"""SQLite integration checks for prefix observation assignment."""

from dataclasses import replace
from ipaddress import ip_network
from uuid import uuid4

import pytest

from netvoyager_analysis.ipam.discovery.assignment import (
    PrefixObservationAssignmentService,
)
from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_database.engine import create_database_engine
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)


@pytest.fixture
def uow_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    session_factory = create_session_factory(engine)

    try:
        yield lambda: NetworkInventoryUnitOfWork(session_factory)
    finally:
        engine.dispose()


def observation(space=None):
    return PrefixObservation(
        local_ref="synthetic-prefix",
        prefix=ip_network("192.0.2.0/24"),
        observation_kind="inventory",
        address_space_id=space,
    )


def candidate(space=None, status="candidate"):
    return PrefixDiscoveryCandidate(
        prefix=ip_network("192.0.2.0/24"),
        address_space_id=space,
        status=status,
    )


def test_new_observation_creates_candidate(uow_factory):
    item = observation()

    with uow_factory() as uow:
        plan = PrefixObservationAssignmentService(uow).assign(
            item, dataset_id=uuid4()
        )
        assert plan.action == "create_candidate"
        assert uow.prefix_discovery.candidate_observation_ids(
            plan.candidate.candidate_id
        ) == (item.observation_id,)
        uow.commit()

    with uow_factory() as uow:
        assert uow.prefix_discovery.get_observation(
            item.observation_id
        ) == item
        assert uow.prefix_discovery.get_candidate(
            plan.candidate.candidate_id
        ) is not None


def test_exact_match_reuses_candidate(uow_factory):
    space = uuid4()
    item = observation(space)
    original = candidate(space)

    with uow_factory() as uow:
        uow.prefix_discovery.add_candidate(original)
        plan = PrefixObservationAssignmentService(uow).assign(
            item, dataset_id=uuid4()
        )

        assert plan.action == "reuse_candidate"
        assert plan.candidate.candidate_id == original.candidate_id


def test_unknown_space_preserves_possible_match(uow_factory):
    original = candidate(uuid4())

    with uow_factory() as uow:
        uow.prefix_discovery.add_candidate(original)
        plan = PrefixObservationAssignmentService(uow).assign(
            observation(), dataset_id=uuid4()
        )

        assert plan.action == "create_candidate"
        assert len(plan.possible_matches) == 1
        assert (
            plan.possible_matches[0].candidate_id
            == original.candidate_id
        )


def test_two_exact_matches_create_new_candidate(uow_factory):
    space = uuid4()
    first, second = candidate(space), candidate(space)

    with uow_factory() as uow:
        uow.prefix_discovery.add_candidate(first)
        uow.prefix_discovery.add_candidate(second)

        plan = PrefixObservationAssignmentService(uow).assign(
            observation(space), dataset_id=uuid4()
        )

        assert plan.action == "create_candidate"
        assert len(plan.possible_matches) == 2
        assert plan.candidate.candidate_id not in {
            first.candidate_id,
            second.candidate_id,
        }


def test_different_known_spaces_do_not_match(uow_factory):
    original = candidate(uuid4())

    with uow_factory() as uow:
        uow.prefix_discovery.add_candidate(original)

        plan = PrefixObservationAssignmentService(uow).assign(
            observation(uuid4()), dataset_id=uuid4()
        )

        assert plan.action == "create_candidate"
        assert plan.possible_matches == ()


def test_rejected_candidate_not_reused(uow_factory):
    space = uuid4()
    original = candidate(space, status="rejected")

    with uow_factory() as uow:
        uow.prefix_discovery.add_candidate(original)

        plan = PrefixObservationAssignmentService(uow).assign(
            observation(space), dataset_id=uuid4()
        )

        assert plan.action == "create_candidate"
        assert plan.candidate.candidate_id != original.candidate_id


def test_reprocessing_same_observation_reuses_original_link(
    uow_factory,
):
    item = observation()
    dataset_id = uuid4()

    with uow_factory() as uow:
        first = PrefixObservationAssignmentService(uow).assign(
            item, dataset_id=dataset_id
        )
        uow.commit()

    with uow_factory() as uow:
        second = PrefixObservationAssignmentService(uow).assign(
            item, dataset_id=dataset_id
        )

        assert (
            second.candidate.candidate_id
            == first.candidate.candidate_id
        )
        assert uow.prefix_discovery.candidate_observation_ids(
            first.candidate.candidate_id
        ) == (item.observation_id,)


def test_conflicting_observation_rejected(uow_factory):
    item = observation()

    with uow_factory() as uow:
        service = PrefixObservationAssignmentService(uow)
        service.assign(item, dataset_id=uuid4())

        conflict = replace(
            item,
            prefix=ip_network("198.51.100.0/24"),
        )

        with pytest.raises(ValueError, match="Conflicting observation"):
            service.assign(conflict, dataset_id=uuid4())


def test_uncommitted_assignment_rolls_back(uow_factory):
    item = observation()

    with uow_factory() as uow:
        plan = PrefixObservationAssignmentService(uow).assign(
            item, dataset_id=uuid4()
        )

    with uow_factory() as uow:
        assert uow.prefix_discovery.get_observation(
            item.observation_id
        ) is None
        assert uow.prefix_discovery.get_candidate(
            plan.candidate.candidate_id
        ) is None
