
"""Correlate site scopes with BGP origin ASNs through canonical prefixes."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from ipaddress import IPv4Network

from netvoyager_core.logging import get_logger
from netvoyager_network.bgp.models import AsPrefix, AutonomousSystem
from netvoyager_network.scope.models import NetworkScope
from netvoyager_network.ipam.models import NetworkPrefix

from ..findings.models import Finding
from ..findings.store import FindingStore
from .store import NetworkPrefixStore

logger = get_logger("netvoyager.analysis.ipam.asn")


def associate_scope_autonomous_systems(
    scopes: Mapping[str, NetworkScope],
    as_prefixes: Iterable[AsPrefix],
    autonomous_systems: Iterable[AutonomousSystem],
    *,
    network_prefix_store: NetworkPrefixStore,
    finding_store: FindingStore,
) -> int:
    """Associate site scopes with ASNs through exact prefix observations.

    Each site receives all distinct origin ASNs observed for its canonical
    prefixes. Duplicate observations do not create duplicate assignments.

    Create findings for:
    - Prefixes associated with multiple ASNs.
    - Sites associated with multiple ASNs.
    - ASNs associated with multiple sites.

    Existing prefix_multiple_sites findings are handled separately.

    Return the number of newly created scope-ASN assignments.
    """
    asns_by_prefix: dict[IPv4Network, set[int]] = defaultdict(set)

    for observation in as_prefixes:
        asns_by_prefix[observation.prefix].add(observation.asn)

    systems_by_asn = {
        system.asn: system
        for system in autonomous_systems
    }

    prefix_sites: dict[IPv4Network, set[str]] = defaultdict(set)
    asn_sites: dict[int, dict[str, set[IPv4Network]]] = defaultdict(
        lambda: defaultdict(set)
    )
    ambiguous_prefixes: dict[IPv4Network, NetworkPrefix] = {}

    added_assignments = 0

    for scope in scopes.values():
        if scope.kind != "site":
            continue

        for prefix_id in scope.prefix_ids:
            canonical_prefix = network_prefix_store.get(prefix_id)

            if canonical_prefix is None:
                raise ValueError(
                    f"Scope {scope.scope_id!r} references an unknown "
                    f"NetworkPrefix ID: {prefix_id}"
                )

            network = canonical_prefix.prefix
            observed_asns = asns_by_prefix.get(network, set())

            prefix_sites[network].add(scope.scope_id)

            if len(observed_asns) > 1:
                ambiguous_prefixes[network] = canonical_prefix

            for asn in observed_asns:
                if asn not in scope.asns:
                    scope.add_asn(asn)
                    added_assignments += 1

                asn_sites[asn][scope.scope_id].add(network)

    # Detect canonical prefixes with multiple origin ASNs.
    for network, canonical_prefix in sorted(ambiguous_prefixes.items()):
        existing = finding_store.for_object(
            "network_prefix",
            canonical_prefix.id,
        )

        if any(f.kind == "prefix_multiple_asns" for f in existing):
            continue

        finding_store.add(
            Finding(
                kind="prefix_multiple_asns",
                severity="warning",
                message=f"Prefix {network} has multiple observed origin ASNs",
                object_type="network_prefix",
                object_id=canonical_prefix.id,
                details={
                    "prefix": network,
                    "asns": tuple(sorted(asns_by_prefix[network])),
                    "sites": tuple(sorted(prefix_sites[network])),
                },
            )
        )

    # Detect sites associated with multiple ASNs.
    for scope in scopes.values():
        if scope.kind != "site" or len(scope.asns) <= 1:
            continue

        existing = finding_store.for_object(
            "network_scope",
            scope.scope_id,
        )

        if any(f.kind == "site_multiple_asns" for f in existing):
            continue

        finding_store.add(
            Finding(
                kind="site_multiple_asns",
                severity="warning",
                message=(
                    f"Site {scope.scope_id} is associated "
                    "with multiple ASNs"
                ),
                object_type="network_scope",
                object_id=scope.scope_id,
                details={
                    "site": scope.scope_id,
                    "asns": tuple(sorted(scope.asns)),
                },
            )
        )

    # Detect ASNs associated with multiple sites.
    for asn, sites in sorted(asn_sites.items()):
        if len(sites) <= 1:
            continue

        system = systems_by_asn.get(asn)

        if system is None:
            raise ValueError(
                f"No AutonomousSystem object for observed ASN {asn}"
            )

        existing = finding_store.for_object(
            "autonomous_system",
            system.id,
        )

        if any(f.kind == "asn_multiple_sites" for f in existing):
            continue

        finding_store.add(
            Finding(
                kind="asn_multiple_sites",
                severity="warning",
                message=f"ASN {asn} is associated with multiple sites",
                object_type="autonomous_system",
                object_id=system.id,
                details={
                    "asn": asn,
                    "sites": tuple(sorted(sites)),
                    "site_prefixes": {
                        site: tuple(sorted(prefixes))
                        for site, prefixes in sorted(sites.items())
                    },
                },
            )
        )

    logger.info(
        "Site ASN correlation completed: scopes=%d | "
        "new_assignments=%d | scope_asn_assignments=%d | "
        "associated_asns=%d",
        sum(scope.kind == "site" for scope in scopes.values()),
        added_assignments,
        sum(
            len(scope.asns)
            for scope in scopes.values()
            if scope.kind == "site"
        ),
        len(asn_sites),
    )

    return added_assignments
