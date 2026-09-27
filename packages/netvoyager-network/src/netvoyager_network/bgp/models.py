"""Shared BGP domain models."""

from dataclasses import dataclass
from ipaddress import IPv4Network, IPv4Address


@dataclass(frozen=True, slots=True)
class AsPrefixes:
    """IPv4 prefixes observed with the same origin ASN."""

    asn: int
    prefixes: tuple[IPv4Network, ...]

@dataclass(frozen=True, slots=True)
class PrefixAsMatch:
    prefix: IPv4Network
    origin_as: int | None
 

@dataclass(frozen=True, slots=True)
class AsSiteEvidence:
    site: str
    management_ip: IPv4Address
    matched_prefix: IPv4Network


@dataclass(frozen=True, slots=True)
class AsSiteAssignment:
    asn: int
    sites: tuple[str, ...]
    evidence: tuple[AsSiteEvidence, ...]


@dataclass(frozen=True, slots=True)
class UnresolvedSiteIp:
    site: str
    management_ip: IPv4Address
    reason: str


@dataclass(frozen=True, slots=True)
class AsSiteAssignmentResult:
    assignments: tuple[AsSiteAssignment, ...]
    unresolved: tuple[UnresolvedSiteIp, ...]
    skipped_devices: int