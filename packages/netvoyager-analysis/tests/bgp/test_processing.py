
"""Tests for BGP route processing and evidence relationships."""

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from uuid import uuid4

from netvoyager_analysis.bgp.processing import process_bgp_routes
from netvoyager_analysis.evidence.store import EvidenceStore


@dataclass(frozen=True)
class FakeBgpRoute:
    """Test observation satisfying the BgpRouteObservation protocol."""

    prefix: IPv4Network
    as_path: tuple[int, ...] | None
    peer: str | None = "prisma_bgp_peer"
    next_hop: IPv4Address | None = None
    line_number: int | None = None
    raw_line: str | None = None


def make_route(
    prefix: str = "10.249.0.0/24",
    as_path: tuple[int, ...] | None = (65534, 65520),
    peer: str | None = "prisma_bgp_peer",
    line_number: int | None = None,
) -> FakeBgpRoute:
    return FakeBgpRoute(
        prefix=IPv4Network(prefix),
        as_path=as_path,
        peer=peer,
        next_hop=IPv4Address("192.168.254.42"),
        line_number=line_number,
    )


def test_process_bgp_route_creates_prefix_and_asn():
    source_id = uuid4()
    evidence_store = EvidenceStore()

    result = process_bgp_routes(
        [make_route()],
        source="panorama",
        source_id=source_id,
        evidence_store=evidence_store,
    )

    assert len(result.as_prefixes) == 1
    assert len(result.autonomous_systems) == 1

    as_prefix = result.as_prefixes[0]
    autonomous_system = result.autonomous_systems[0]

    assert as_prefix.source_id == source_id
    assert as_prefix.prefix == IPv4Network("10.249.0.0/24")
    assert as_prefix.asn == 65520
    assert as_prefix.as_path == (65534, 65520)
    assert as_prefix.id.version == 5

    assert autonomous_system.asn == 65520
    assert as_prefix.prefix in autonomous_system.prefixes


def test_as_prefix_identity_is_stable_across_runs():
    source_id = uuid4()

    first = process_bgp_routes(
        [make_route()],
        source="panorama",
        source_id=source_id,
        evidence_store=EvidenceStore(),
    )

    second = process_bgp_routes(
        [make_route(as_path=(65534, 65520, 65520))],
        source="panorama",
        source_id=source_id,
        evidence_store=EvidenceStore(),
    )

    assert first.as_prefixes[0].id == second.as_prefixes[0].id


def test_duplicate_observations_preserve_all_evidence():
    source_id = uuid4()
    evidence_store = EvidenceStore()

    routes = [
        make_route(line_number=10),
        make_route(line_number=20),
    ]

    result = process_bgp_routes(
        routes,
        source="panorama",
        source_id=source_id,
        evidence_store=evidence_store,
    )

    assert len(result.as_prefixes) == 2
    assert result.as_prefixes[0].id == result.as_prefixes[1].id

    assert len(evidence_store.records) == 2

    as_prefix_id = result.as_prefixes[0].id
    autonomous_system_id = result.autonomous_systems[0].id

    prefix_evidence = evidence_store.for_object(
        "as_prefix",
        as_prefix_id,
    )

    asn_evidence = evidence_store.for_object(
        "autonomous_system",
        autonomous_system_id,
    )

    assert len(prefix_evidence) == 2
    assert len(asn_evidence) == 2

    assert {record.details["line"] for record in asn_evidence} == {
        10,
        20,
    }


def test_local_route_uses_local_asn():
    evidence_store = EvidenceStore()

    result = process_bgp_routes(
        [
            make_route(
                as_path=(),
                peer="local",
            )
        ],
        source="panorama",
        source_id=uuid4(),
        evidence_store=evidence_store,
        local_asn=64813,
    )

    assert result.local_route_count == 1
    assert result.unknown_origin_count == 0
    assert len(result.as_prefixes) == 1
    assert result.as_prefixes[0].asn == 64813


def test_unknown_origin_preserves_evidence():
    evidence_store = EvidenceStore()

    result = process_bgp_routes(
        [
            make_route(
                as_path=None,
                peer="prisma_bgp_peer",
            )
        ],
        source="panorama",
        source_id=uuid4(),
        evidence_store=evidence_store,
    )

    assert result.unknown_origin_count == 1
    assert len(result.as_prefixes) == 0
    assert len(result.autonomous_systems) == 0

    assert len(evidence_store.records) == 1
    assert evidence_store.records[0].details["origin_asn"] is None


def test_different_sources_have_different_prefix_identities():
    first = process_bgp_routes(
        [make_route()],
        source="firewall-a",
        source_id=uuid4(),
        evidence_store=EvidenceStore(),
    )

    second = process_bgp_routes(
        [make_route()],
        source="firewall-b",
        source_id=uuid4(),
        evidence_store=EvidenceStore(),
    )

    assert first.as_prefixes[0].id != second.as_prefixes[0].id
