"""Tests for site-to-ASN correlation through canonical network prefixes."""

from ipaddress import IPv4Network
from uuid import uuid4

import pytest

from netvoyager_analysis.findings.store import FindingStore
from netvoyager_analysis.ipam.asn import (
    associate_scope_autonomous_systems,
)
from netvoyager_analysis.ipam.store import NetworkPrefixStore
from netvoyager_network.bgp.models import AsPrefix, AutonomousSystem
from netvoyager_network.scope.models import NetworkScope


def create_scope(
    site: str,
    *prefixes: str,
    prefix_store: NetworkPrefixStore,
) -> NetworkScope:
    """Create a site scope with canonical prefix associations."""
    scope = NetworkScope(
        scope_id=site,
        name=site,
        kind="site",
    )

    for prefix in prefixes:
        canonical, _ = prefix_store.get_or_create(
            IPv4Network(prefix)
        )
        scope.add_prefix(canonical.id)

    return scope


def create_bgp_data(
    *observations: tuple[str, int],
) -> tuple[list[AsPrefix], list[AutonomousSystem]]:
    """Create BGP observations and unique autonomous systems."""
    as_prefixes: list[AsPrefix] = []
    systems: dict[int, AutonomousSystem] = {}

    for prefix, asn in observations:
        network = IPv4Network(prefix)

        as_prefixes.append(
            AsPrefix(
                asn=asn,
                prefix=network,
            )
        )

        if asn not in systems:
            systems[asn] = AutonomousSystem(asn=asn)

        if network not in systems[asn].prefixes:
            systems[asn].add_prefix(network)

    return as_prefixes, list(systems.values())


def run_correlation(
    scopes: dict[str, NetworkScope],
    observations: list[AsPrefix],
    systems: list[AutonomousSystem],
    prefix_store: NetworkPrefixStore,
    finding_store: FindingStore,
) -> int:
    """Run ASN correlation with the supplied test objects."""
    return associate_scope_autonomous_systems(
        scopes,
        observations,
        systems,
        network_prefix_store=prefix_store,
        finding_store=finding_store,
    )


def test_one_prefix_one_asn_one_site() -> None:
    """Associate one ASN without generating findings."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = create_scope(
        "Site-A",
        "10.10.10.0/24",
        prefix_store=prefix_store,
    )

    observations, systems = create_bgp_data(
        ("10.10.10.0/24", 65001),
    )

    added = run_correlation(
        {"Site-A": scope},
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    assert added == 1
    assert scope.asns == frozenset({65001})
    assert len(finding_store.findings) == 0


def test_multiple_prefixes_same_asn() -> None:
    """Multiple prefixes from one ASN produce one ASN assignment."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = create_scope(
        "Site-A",
        "10.10.10.0/24",
        "10.10.20.0/24",
        prefix_store=prefix_store,
    )

    observations, systems = create_bgp_data(
        ("10.10.10.0/24", 65001),
        ("10.10.20.0/24", 65001),
    )

    added = run_correlation(
        {"Site-A": scope},
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    assert added == 1
    assert scope.asns == frozenset({65001})
    assert len(finding_store.findings) == 0


def test_prefix_multiple_asns() -> None:
    """Preserve all ASNs and report an ambiguous prefix."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = create_scope(
        "Site-A",
        "10.10.10.0/24",
        prefix_store=prefix_store,
    )

    observations, systems = create_bgp_data(
        ("10.10.10.0/24", 65001),
        ("10.10.10.0/24", 65002),
    )

    added = run_correlation(
        {"Site-A": scope},
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    assert added == 2
    assert scope.asns == frozenset({65001, 65002})

    prefix_findings = finding_store.by_kind(
        "prefix_multiple_asns"
    )
    site_findings = finding_store.by_kind(
        "site_multiple_asns"
    )

    assert len(prefix_findings) == 1
    assert len(site_findings) == 1
    assert prefix_findings[0].details["asns"] == (65001, 65002)


def test_asn_multiple_sites() -> None:
    """Detect one ASN associated with multiple sites."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scopes = {
        "Site-A": create_scope(
            "Site-A",
            "10.10.10.0/24",
            prefix_store=prefix_store,
        ),
        "Site-B": create_scope(
            "Site-B",
            "10.20.10.0/24",
            prefix_store=prefix_store,
        ),
    }

    observations, systems = create_bgp_data(
        ("10.10.10.0/24", 65001),
        ("10.20.10.0/24", 65001),
    )

    added = run_correlation(
        scopes,
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    assert added == 2
    assert scopes["Site-A"].asns == frozenset({65001})
    assert scopes["Site-B"].asns == frozenset({65001})

    findings = finding_store.by_kind("asn_multiple_sites")

    assert len(findings) == 1
    assert findings[0].details["asn"] == 65001
    assert findings[0].details["sites"] == (
        "Site-A",
        "Site-B",
    )


def test_site_multiple_asns() -> None:
    """Detect one site associated with multiple different ASNs."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = create_scope(
        "Site-A",
        "10.10.10.0/24",
        "10.20.10.0/24",
        prefix_store=prefix_store,
    )

    observations, systems = create_bgp_data(
        ("10.10.10.0/24", 65001),
        ("10.20.10.0/24", 65002),
    )

    added = run_correlation(
        {"Site-A": scope},
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    assert added == 2
    assert scope.asns == frozenset({65001, 65002})

    assert len(
        finding_store.by_kind("site_multiple_asns")
    ) == 1

    assert len(
        finding_store.by_kind("prefix_multiple_asns")
    ) == 0


def test_duplicate_bgp_observations() -> None:
    """Repeated observations must not duplicate ASN assignments."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = create_scope(
        "Site-A",
        "10.10.10.0/24",
        prefix_store=prefix_store,
    )

    observations, systems = create_bgp_data(
        ("10.10.10.0/24", 65001),
        ("10.10.10.0/24", 65001),
        ("10.10.10.0/24", 65001),
    )

    added = run_correlation(
        {"Site-A": scope},
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    assert added == 1
    assert scope.asns == frozenset({65001})
    assert len(finding_store.findings) == 0


def test_prefix_without_asn_observation() -> None:
    """Canonical prefixes without BGP observations remain unassigned."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = create_scope(
        "Site-A",
        "10.10.10.0/24",
        prefix_store=prefix_store,
    )

    added = run_correlation(
        {"Site-A": scope},
        [],
        [],
        prefix_store,
        finding_store,
    )

    assert added == 0
    assert scope.asns == frozenset()
    assert len(finding_store.findings) == 0


def test_repeated_correlation_is_idempotent() -> None:
    """Repeated execution must not duplicate assignments or findings."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = create_scope(
        "Site-A",
        "10.10.10.0/24",
        prefix_store=prefix_store,
    )

    observations, systems = create_bgp_data(
        ("10.10.10.0/24", 65001),
        ("10.10.10.0/24", 65002),
    )

    scopes = {"Site-A": scope}

    first = run_correlation(
        scopes,
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    initial_findings = len(finding_store.findings)

    second = run_correlation(
        scopes,
        observations,
        systems,
        prefix_store,
        finding_store,
    )

    assert first == 2
    assert second == 0
    assert len(finding_store.findings) == initial_findings
    assert scope.asns == frozenset({65001, 65002})


def test_unknown_canonical_prefix_raises_error() -> None:
    """Reject a scope referencing a missing canonical prefix."""
    prefix_store = NetworkPrefixStore()
    finding_store = FindingStore()

    scope = NetworkScope(
        scope_id="Site-A",
        name="Site-A",
        kind="site",
    )
    scope.add_prefix(uuid4())

    with pytest.raises(ValueError, match="unknown NetworkPrefix"):
        run_correlation(
            {"Site-A": scope},
            [],
            [],
            prefix_store,
            finding_store,
        )