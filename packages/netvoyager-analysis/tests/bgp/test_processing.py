
"""Tests for BGP route processing with SQL-backed provenance."""

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from uuid import UUID, uuid4

import pytest

from netvoyager_analysis.bgp.processing import process_bgp_routes
from netvoyager_database.engine import create_database_engine
from netvoyager_database.repositories.evidence import SqlEvidenceRepository
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_intelligence.evidence import EvidenceRecord


@dataclass(frozen=True)
class FakeBgpRoute:
    """Synthetic observation satisfying the BGP route protocol."""

    prefix: IPv4Network
    as_path: tuple[int, ...] | None
    peer: str | None = "synthetic_peer"
    next_hop: IPv4Address | None = None
    line_number: int | None = None
    raw_line: str | None = None


def make_route(
    prefix: str = "192.0.2.0/24",
    as_path: tuple[int, ...] | None = (64512, 64513),
    peer: str | None = "synthetic_peer",
    line_number: int | None = None,
) -> FakeBgpRoute:
    """Build a fictional BGP observation using documentation addresses."""
    return FakeBgpRoute(
        prefix=IPv4Network(prefix),
        as_path=as_path,
        peer=peer,
        next_hop=IPv4Address("198.51.100.1"),
        line_number=line_number,
    )


@pytest.fixture
def evidence_store():
    """Provide a fresh in-memory SQLite evidence repository per test."""
    engine = create_database_engine("sqlite:///:memory:")
    create_schema(engine)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            yield SqlEvidenceRepository(session)
    finally:
        engine.dispose()


def test_process_bgp_route_creates_prefix_and_asn(evidence_store):
    source_id = uuid4()
    result = process_bgp_routes(
        [make_route()],
        source="synthetic_bgp",
        source_id=source_id,
        evidence_store=evidence_store,
    )

    assert len(result.as_prefixes) == 1
    assert len(result.autonomous_systems) == 1
    as_prefix = result.as_prefixes[0]
    autonomous_system = result.autonomous_systems[0]

    assert as_prefix.source_id == source_id
    assert as_prefix.prefix == IPv4Network("192.0.2.0/24")
    assert as_prefix.asn == 64513
    assert as_prefix.as_path == (64512, 64513)
    assert as_prefix.id.version == 5
    assert autonomous_system.asn == 64513
    assert as_prefix.prefix in autonomous_system.prefixes

    evidence = evidence_store.for_object(
        as_prefix.id, object_type="as_prefix"
    )
    assert len(evidence) == 1
    assert evidence[0].details["prefix"] == "192.0.2.0/24"
    assert evidence[0].details["as_path"] == [64512, 64513]
    assert evidence[0].details["next_hop"] == "198.51.100.1"
    assert evidence_store.for_object(
        autonomous_system.id, object_type="autonomous_system"
    )[0].id == evidence[0].id


def test_as_prefix_identity_is_stable_across_runs(evidence_store):
    source_id = uuid4()
    first = process_bgp_routes(
        [make_route()],
        source="synthetic_bgp",
        source_id=source_id,
        evidence_store=evidence_store,
    )
    second = process_bgp_routes(
        [make_route(as_path=(64512, 64513, 64513))],
        source="synthetic_bgp",
        source_id=source_id,
        evidence_store=evidence_store,
    )
    assert first.as_prefixes[0].id == second.as_prefixes[0].id
    assert len(evidence_store.for_object(
        first.as_prefixes[0].id, object_type="as_prefix"
    )) == 2


def test_duplicate_observations_preserve_all_evidence(evidence_store):
    result = process_bgp_routes(
        [make_route(line_number=10), make_route(line_number=20)],
        source="synthetic_bgp",
        source_id=uuid4(),
        evidence_store=evidence_store,
    )
    assert len(result.as_prefixes) == 2
    assert result.as_prefixes[0].id == result.as_prefixes[1].id
    as_prefix_id = result.as_prefixes[0].id
    autonomous_system_id = result.autonomous_systems[0].id
    prefix_evidence = evidence_store.for_object(
        as_prefix_id, object_type="as_prefix"
    )
    asn_evidence = evidence_store.for_object(
        autonomous_system_id, object_type="autonomous_system"
    )
    assert len(prefix_evidence) == 2
    assert len(asn_evidence) == 2
    assert {record.id for record in prefix_evidence} == {
        record.id for record in asn_evidence
    }
    assert {record.details["line"] for record in asn_evidence} == {10, 20}


def test_local_route_uses_local_asn(evidence_store):
    result = process_bgp_routes(
        [make_route(as_path=(), peer="local")],
        source="synthetic_bgp",
        source_id=uuid4(),
        evidence_store=evidence_store,
        local_asn=64514,
    )
    assert result.local_route_count == 1
    assert result.unknown_origin_count == 0
    assert len(result.as_prefixes) == 1
    assert result.as_prefixes[0].asn == 64514


def test_unknown_origin_preserves_evidence(evidence_store):
    """An unlinked observation remains retrievable by its evidence UUID."""
    recorded_ids: list[UUID] = []

    class RecordingEvidenceRepository:
        """Forward writes to SQL and capture generated evidence IDs."""

        def add(self, record: EvidenceRecord) -> None:
            recorded_ids.append(record.id)
            evidence_store.add(record)

        def link(
            self, evidence_id: UUID, object_type: str, object_id: UUID
        ) -> None:
            evidence_store.link(evidence_id, object_type, object_id)

    result = process_bgp_routes(
        [make_route(as_path=None)],
        source="synthetic_bgp",
        source_id=uuid4(),
        evidence_store=RecordingEvidenceRepository(),
    )
    assert result.unknown_origin_count == 1
    assert len(result.as_prefixes) == 0
    assert len(result.autonomous_systems) == 0
    assert len(recorded_ids) == 1
    persisted = evidence_store.get(recorded_ids[0])
    assert persisted is not None
    assert persisted.details["origin_asn"] is None
    assert persisted.details["prefix"] == "192.0.2.0/24"


def test_different_sources_have_different_prefix_identities(evidence_store):
    first = process_bgp_routes(
        [make_route()],
        source="synthetic_firewall_a",
        source_id=uuid4(),
        evidence_store=evidence_store,
    )
    second = process_bgp_routes(
        [make_route()],
        source="synthetic_firewall_b",
        source_id=uuid4(),
        evidence_store=evidence_store,
    )
    assert first.as_prefixes[0].id != second.as_prefixes[0].id
