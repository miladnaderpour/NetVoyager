
"""SQLite-backed tests for prefix candidate correlation service."""

from ipaddress import ip_network
from uuid import uuid4

from netvoyager_analysis.ipam.discovery.correlation import correlate_prefix_candidates
import pytest

from netvoyager_analysis.ipam.discovery.persistent_correlation import (
    PrefixCandidateCorrelationService,
)
from netvoyager_database.engine import create_database_engine
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)
from netvoyager_network.ipam.discovery.relationships import (
    PrefixDiscoveryCandidateRelationship,
)


@pytest.fixture
def uow_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)

    try:
        yield lambda: NetworkInventoryUnitOfWork(factory)
    finally:
        engine.dispose()


def candidate(
    prefix="192.0.2.0/24",
    space=None,
    status="candidate",
):
    return PrefixDiscoveryCandidate(
        prefix=ip_network(prefix),
        address_space_id=space,
        status=status,
    )


def test_proposals_persist_and_rerun_is_idempotent(uow_factory):
    a, b = candidate(), candidate()

    with uow_factory() as uow:
        uow.prefix_discovery.add_candidate(a)
        uow.prefix_discovery.add_candidate(b)
        uow.commit()

    with uow_factory() as uow:
        result = PrefixCandidateCorrelationService(uow).correlate(
            "192.0.2.0/24"
        )
        assert len(result.proposed) == 1
        uow.commit()

    with uow_factory() as uow:
        result = PrefixCandidateCorrelationService(uow).correlate(
            "192.0.2.0/24"
        )
        assert result.proposed == ()

        saved = uow.prefix_discovery.find_relationship(
            a.candidate_id,
            b.candidate_id,
        )
        assert saved is not None
        assert saved.status == "possible"


def test_rejected_relationship_is_not_overwritten(uow_factory):
    a, b = candidate(), candidate()

    rejected = PrefixDiscoveryCandidateRelationship(
        a.candidate_id,
        b.candidate_id,
        status="rejected",
    )

    with uow_factory() as uow:
        repo = uow.prefix_discovery
        repo.add_candidate(a)
        repo.add_candidate(b)
        repo.add_relationship(rejected)
        uow.commit()

    with uow_factory() as uow:
        result = PrefixCandidateCorrelationService(uow).correlate(
            "192.0.2.0/24"
        )
        assert result.proposed == ()
        assert uow.prefix_discovery.get_relationship(
            rejected.relationship_id
        ).status == "rejected"


def test_unknown_space_can_correlate_but_different_known_spaces_cannot(
    uow_factory,
):
    a = candidate(space=uuid4())
    b = candidate(space=None)
    c = candidate(space=uuid4())

    with uow_factory() as uow:
        for item in (a, b, c):
            uow.prefix_discovery.add_candidate(item)

        result = PrefixCandidateCorrelationService(uow).correlate(
            "192.0.2.0/24"
        )

        pairs = {
            frozenset(
                (r.candidate_a_id, r.candidate_b_id)
            )
            for r in result.proposed
        }

        assert pairs == {
            frozenset((a.candidate_id, b.candidate_id)),
            frozenset((b.candidate_id, c.candidate_id)),
        }


def test_rollback_discards_relationship(uow_factory):
    a, b = candidate(), candidate()

    with uow_factory() as uow:
        uow.prefix_discovery.add_candidate(a)
        uow.prefix_discovery.add_candidate(b)
        uow.commit()

    with uow_factory() as uow:
        result = PrefixCandidateCorrelationService(uow).correlate(
            "192.0.2.0/24"
        )
        assert len(result.proposed) == 1

    with uow_factory() as uow:
        assert uow.prefix_discovery.find_relationship(
            a.candidate_id,
            b.candidate_id,
        ) is None


def test_only_target_cidr_is_correlated(uow_factory):
    a, b = candidate(), candidate()
    c = candidate("198.51.100.0/24")
    d = candidate("198.51.100.0/24")

    with uow_factory() as uow:
        for item in (a, b, c, d):
            uow.prefix_discovery.add_candidate(item)

        result = PrefixCandidateCorrelationService(uow).correlate(
            "192.0.2.0/24"
        )

        assert len(result.proposed) == 1
        assert uow.prefix_discovery.find_relationship(
            c.candidate_id,
            d.candidate_id,
        ) is None

def test_many_distinct_cidrs_do_not_produce_relationships():
    from ipaddress import IPv4Network

    items = [
        PrefixDiscoveryCandidate(
            prefix=IPv4Network((index << 8, 24))
        )
        for index in range(2000)
    ]

    assert correlate_prefix_candidates(items).proposed == ()