
"""SQLite integration tests for canonical IPAM persistence."""

from ipaddress import ip_network
from uuid import uuid4

import pytest

from netvoyager_database.engine import create_database_engine
from netvoyager_database.exceptions import RepositoryConflictError
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_network.ipam.address_space import (
    AddressSpace,
    GLOBAL_ADDRESS_SPACE,
)
from netvoyager_network.ipam.models import NetworkPrefix


@pytest.fixture
def uow_factory():
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)

    try:
        yield lambda: NetworkInventoryUnitOfWork(factory)
    finally:
        engine.dispose()


def test_address_space_round_trip(uow_factory):
    with uow_factory() as uow:
        uow.network_prefixes.add_address_space(
            GLOBAL_ADDRESS_SPACE
        )
        uow.commit()

    with uow_factory() as uow:
        assert uow.network_prefixes.get_address_space(
            GLOBAL_ADDRESS_SPACE.id
        ) == GLOBAL_ADDRESS_SPACE


def test_network_prefix_round_trip_and_exact_lookup(uow_factory):
    prefix = NetworkPrefix(ip_network("192.0.2.0/24"))

    with uow_factory() as uow:
        repo = uow.network_prefixes
        repo.add_address_space(GLOBAL_ADDRESS_SPACE)
        repo.add_prefix(prefix)
        uow.commit()

    with uow_factory() as uow:
        repo = uow.network_prefixes

        assert repo.get_prefix(prefix.id) == prefix
        assert repo.find_prefix(
            "192.0.2.15/24",
            GLOBAL_ADDRESS_SPACE.id,
        ) == prefix


def test_same_cidr_can_exist_in_different_spaces(uow_factory):
    other = AddressSpace(uuid4(), "LAB-A")

    first = NetworkPrefix(
        ip_network("192.0.2.0/24"),
        GLOBAL_ADDRESS_SPACE.id,
    )
    second = NetworkPrefix(
        ip_network("192.0.2.0/24"),
        other.id,
    )

    assert first.id != second.id

    with uow_factory() as uow:
        repo = uow.network_prefixes
        repo.add_address_space(GLOBAL_ADDRESS_SPACE)
        repo.add_address_space(other)
        repo.add_prefix(first)
        repo.add_prefix(second)
        uow.commit()

    with uow_factory() as uow:
        repo = uow.network_prefixes
        assert repo.get_prefix(first.id) == first
        assert repo.get_prefix(second.id) == second


def test_duplicate_prefix_is_rejected(uow_factory):
    prefix = NetworkPrefix(ip_network("198.51.100.0/24"))

    with uow_factory() as uow:
        repo = uow.network_prefixes
        repo.add_address_space(GLOBAL_ADDRESS_SPACE)
        repo.add_prefix(prefix)
        uow.commit()

    with uow_factory() as uow:
        with pytest.raises(RepositoryConflictError):
            uow.network_prefixes.add_prefix(prefix)


def test_unknown_address_space_is_rejected(uow_factory):
    prefix = NetworkPrefix(
        ip_network("203.0.113.0/24"),
        uuid4(),
    )

    with uow_factory() as uow:
        with pytest.raises(RepositoryConflictError):
            uow.network_prefixes.add_prefix(prefix)


def test_ipv6_network_prefix_round_trip(uow_factory):
    prefix = NetworkPrefix(ip_network("2001:db8:1::/48"))

    with uow_factory() as uow:
        repo = uow.network_prefixes
        repo.add_address_space(GLOBAL_ADDRESS_SPACE)
        repo.add_prefix(prefix)
        uow.commit()

    with uow_factory() as uow:
        assert uow.network_prefixes.get_prefix(prefix.id) == prefix


def test_uncommitted_records_are_rolled_back(uow_factory):
    prefix = NetworkPrefix(ip_network("203.0.113.0/24"))

    with uow_factory() as uow:
        repo = uow.network_prefixes
        repo.add_address_space(GLOBAL_ADDRESS_SPACE)
        repo.add_prefix(prefix)

    with uow_factory() as uow:
        repo = uow.network_prefixes
        assert repo.get_prefix(prefix.id) is None
        assert repo.get_address_space(
            GLOBAL_ADDRESS_SPACE.id
        ) is None
