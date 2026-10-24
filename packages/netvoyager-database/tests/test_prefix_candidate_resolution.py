
"""Integration tests for resolving prefix discovery candidates."""

from dataclasses import replace
from ipaddress import ip_network
from uuid import uuid4

import pytest

from netvoyager_database.engine import create_database_engine
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.exceptions import RepositoryConflictError
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_network.ipam.address_space import (
    GLOBAL_ADDRESS_SPACE,
)
from netvoyager_network.ipam.models import NetworkPrefix
from netvoyager_network.ipam.discovery.models import (
    PrefixDiscoveryCandidate,
)


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


def test_candidate_resolves_to_existing_canonical_prefix(uow_factory):
    """Resolution preserves candidate identity and survives commit."""
    prefix = NetworkPrefix(
        prefix=ip_network("192.0.2.0/24"),
        address_space_id=GLOBAL_ADDRESS_SPACE.id,
    )

    candidate = PrefixDiscoveryCandidate(
        prefix=prefix.prefix,
        address_space_id=prefix.address_space_id,
    )

    with uow_factory() as uow:
        uow.network_prefixes.add_address_space(
            GLOBAL_ADDRESS_SPACE
        )
        uow.network_prefixes.add_prefix(prefix)
        uow.prefix_discovery.add_candidate(candidate)
        uow.commit()

    with uow_factory() as uow:
        resolved = replace(
            candidate,
            status="resolved",
            resolved_prefix_id=prefix.id,
        )

        uow.prefix_discovery.save_candidate(resolved)
        uow.commit()

    with uow_factory() as uow:
        saved = uow.prefix_discovery.get_candidate(
            candidate.candidate_id
        )

        assert saved is not None
        assert saved.candidate_id == candidate.candidate_id
        assert saved.status == "resolved"
        assert saved.resolved_prefix_id == prefix.id

        assert uow.prefix_discovery.candidates_for_prefix(
            prefix.id
        ) == (resolved,)

        assert uow.network_prefixes.get_prefix(prefix.id) == prefix


def test_resolution_rejects_different_cidr(uow_factory):
    """Candidate CIDR must match the canonical prefix."""
    canonical = NetworkPrefix(
        prefix=ip_network("192.0.2.0/24"),
    )

    candidate = PrefixDiscoveryCandidate(
        prefix=ip_network("198.51.100.0/24"),
        address_space_id=GLOBAL_ADDRESS_SPACE.id,
    )

    with uow_factory() as uow:
        uow.network_prefixes.add_address_space(
            GLOBAL_ADDRESS_SPACE
        )
        uow.network_prefixes.add_prefix(canonical)
        uow.prefix_discovery.add_candidate(candidate)
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(RepositoryConflictError):
            uow.prefix_discovery.save_candidate(
                replace(
                    candidate,
                    status="resolved",
                    resolved_prefix_id=canonical.id,
                )
            )


def test_resolution_rejects_different_address_space(uow_factory):
    """Different known address spaces cannot share canonical identity."""
    canonical = NetworkPrefix(
        prefix=ip_network("192.0.2.0/24"),
    )

    candidate = PrefixDiscoveryCandidate(
        prefix=canonical.prefix,
        address_space_id=uuid4(),
    )

    with uow_factory() as uow:
        uow.network_prefixes.add_address_space(
            GLOBAL_ADDRESS_SPACE
        )
        uow.network_prefixes.add_prefix(canonical)
        uow.prefix_discovery.add_candidate(candidate)
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(RepositoryConflictError):
            uow.prefix_discovery.save_candidate(
                replace(
                    candidate,
                    status="resolved",
                    resolved_prefix_id=canonical.id,
                )
            )


def test_uncommitted_resolution_is_rolled_back(uow_factory):
    """Candidate remains unresolved when transaction is not committed."""
    canonical = NetworkPrefix(
        prefix=ip_network("203.0.113.0/24"),
    )

    candidate = PrefixDiscoveryCandidate(
        prefix=canonical.prefix,
        address_space_id=canonical.address_space_id,
    )

    with uow_factory() as uow:
        uow.network_prefixes.add_address_space(
            GLOBAL_ADDRESS_SPACE
        )
        uow.network_prefixes.add_prefix(canonical)
        uow.prefix_discovery.add_candidate(candidate)
        uow.commit()

    with uow_factory() as uow:
        uow.prefix_discovery.save_candidate(
            replace(
                candidate,
                status="resolved",
                resolved_prefix_id=canonical.id,
            )
        )
        # Intentionally no commit.

    with uow_factory() as uow:
        saved = uow.prefix_discovery.get_candidate(
            candidate.candidate_id
        )

        assert saved is not None
        assert saved.status == "candidate"
        assert saved.resolved_prefix_id is None
