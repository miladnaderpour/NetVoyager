"""Associate observed origin ASNs with inventory sites."""

import logging
from collections.abc import Iterable
from ipaddress import IPv4Address, IPv4Network

from netvoyager_network.device.models import NetworkDevice

from .grouping import RouteWithAsPath
from .matching import find_most_specific_matches
from .models import (
    AsSiteAssignment,
    AsSiteAssignmentResult,
    AsSiteEvidence,
    UnresolvedSiteIp,
)


logger = logging.getLogger("netvoyager.network.bgp.site_assignment")


def _site_ips(
    devices: tuple[NetworkDevice, ...],
) -> tuple[tuple[str, IPv4Address], ...]:
    """Deduplicate shared management IPs within each site."""
    pairs = {
        (device.site, device.management_ip)
        for device in devices
        if device.site is not None and device.management_ip is not None
    }
    return tuple(sorted(pairs, key=lambda pair: (pair[0], int(pair[1]))))


def _build_assignments(
    evidence_by_as: dict[int, list[AsSiteEvidence]],
) -> tuple[AsSiteAssignment, ...]:
    assignments: list[AsSiteAssignment] = []

    for asn, evidence in sorted(evidence_by_as.items()):
        ordered_evidence = tuple(
            sorted(
                evidence,
                key=lambda item: (
                    item.site,
                    int(item.management_ip),
                    int(item.matched_prefix.network_address),
                ),
            )
        )
        assignments.append(
            AsSiteAssignment(
                asn=asn,
                sites=tuple(sorted({item.site for item in ordered_evidence})),
                evidence=ordered_evidence,
            )
        )

    return tuple(assignments)


def assign_sites_to_asns(
    devices: Iterable[NetworkDevice],
    routes: Iterable[RouteWithAsPath],
    scope: IPv4Network,
) -> AsSiteAssignmentResult:
    """Match inventory IPs to routes and collect sites by origin ASN."""
    device_list = tuple(devices)
    scoped_routes = tuple(
        route for route in routes if route.prefix.subnet_of(scope)
    )

    evidence_by_as: dict[int, list[AsSiteEvidence]] = {}
    unresolved: list[UnresolvedSiteIp] = []

    for site, address in _site_ips(device_list):
        matches = find_most_specific_matches(address, scoped_routes)

        if not matches:
            unresolved.append(
                UnresolvedSiteIp(site, address, "No matching BGP prefix")
            )
            continue

        if len(matches) > 1:
            unresolved.append(
                UnresolvedSiteIp(site, address, "Multiple best-match ASNs")
            )
            continue

        match = matches[0]
        if match.origin_as is None:
            unresolved.append(
                UnresolvedSiteIp(site, address, "Best match is a local route")
            )
            continue

        evidence_by_as.setdefault(match.origin_as, []).append(
            AsSiteEvidence(
                site=site,
                management_ip=address,
                matched_prefix=match.prefix,
            )
        )

    result = AsSiteAssignmentResult(
        assignments=_build_assignments(evidence_by_as),
        unresolved=tuple(unresolved),
        skipped_devices=sum(
            device.site is None or device.management_ip is None
            for device in device_list
        ),
    )

    logger.info(
        "Inventory sites matched to origin ASNs",
        extra={
            "assignment_count": len(result.assignments),
            "unresolved_count": len(result.unresolved),
            "skipped_device_count": result.skipped_devices,
            "shared_asn_count": sum(
                len(assignment.sites) > 1
                for assignment in result.assignments
            ),
        },
    )
    return result