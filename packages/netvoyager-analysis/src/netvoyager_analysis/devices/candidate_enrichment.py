
"""Enrich provisional device candidates from source observations.

Candidate enrichment fills missing inventory attributes without applying
canonical attribute authority or changing physical-device identity.

Conflicting non-empty attributes are preserved and reported as Findings.

This module performs no database writes, candidate matching, canonical
reconciliation, or transaction management.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from ipaddress import IPv4Address
from typing import Any

from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.devices.observations import DeviceObservation
from netvoyager_intelligence.findings import Finding
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


FINDING_KIND = "device_candidate_attribute_conflict"

INVENTORY_ATTRIBUTES = (
    "site",
    "role",
    "primary_ipv4",
    "manufacturer",
    "model",
    "software_version",
    "asset_tag",
)


@dataclass(frozen=True, slots=True)
class CandidateEnrichmentResult:
    """Proposed candidate snapshot and attribute conflict findings."""

    candidate: DeviceDiscoveryCandidate
    changed_fields: tuple[str, ...]
    findings: tuple[Finding, ...]


def _normalized_value(value: object) -> object | None:
    """Normalize values for provisional attribute comparison.

    Empty strings are treated as missing values. Non-empty strings
    are stripped for comparison but original values are preserved
    in candidate snapshots.

    IPv4Address values are compared using their canonical form.
    """
    if value is None:
        return None

    if isinstance(value, str):
        normalized = value.strip()
        return normalized.casefold() if normalized else None

    return value


def _observation_value(
    observation: DeviceObservation,
    attribute: str,
) -> Any:
    """Read a supported inventory attribute from an observation."""
    value = getattr(observation, attribute)

    if attribute == "primary_ipv4":
        if value is None:
            return None

        if isinstance(value, IPv4Address):
            return value

        return IPv4Address(value)

    return value


def _finding_value(value: object) -> str | None:
    """Convert a compared attribute into JSON-compatible text."""
    if value is None:
        return None

    return str(value)


def enrich_device_candidate(
    candidate: DeviceDiscoveryCandidate,
    observation: DeviceObservation,
    *,
    source: SourceRef,
) -> CandidateEnrichmentResult:
    """Enrich an already matched candidate with source-reported fields.

    The caller must establish candidate identity before invoking this
    function. Serial, hostname, and name are not reconciled here.

    Rules:
        - Missing existing values may be populated.
        - Identical values are preserved.
        - Conflicting values leave the candidate unchanged for that field.
        - Missing incoming values never erase existing information.
        - Rejected and retired candidates cannot be enriched.
        - Candidate identity and lifecycle remain unchanged.

    A conflict creates a proposed Finding. The application layer owns
    persistence and must prevent duplicate findings on repeated imports.
    """
    if candidate.status in {"rejected", "retired"}:
        raise ValueError(
            "Cannot enrich a rejected or retired discovery candidate"
        )

    changes: dict[str, object] = {}
    findings: list[Finding] = []

    for attribute in INVENTORY_ATTRIBUTES:
        existing = getattr(candidate, attribute)
        incoming = _observation_value(observation, attribute)

        normalized_existing = _normalized_value(existing)
        normalized_incoming = _normalized_value(incoming)

        if normalized_incoming is None:
            continue

        if normalized_existing is None:
            changes[attribute] = incoming
            continue

        if normalized_existing == normalized_incoming:
            continue

        findings.append(
            Finding(
                kind=FINDING_KIND,
                severity="warning",
                message=(
                    "Conflicting device discovery candidate "
                    f"attribute: {attribute}"
                ),
                object_type="device_discovery_candidate",
                object_id=candidate.candidate_id,
                details={
                    "attribute": attribute,
                    "existing_value": _finding_value(existing),
                    "incoming_value": _finding_value(incoming),
                    "source_id": source.source_id,
                    "source_method": source.method,
                    "observation_id": str(
                        observation.observation_id
                    ),
                    "observation_local_ref": observation.local_ref,
                },
            )
        )

    updated = (
        replace(candidate, **changes)
        if changes
        else candidate
    )

    return CandidateEnrichmentResult(
        candidate=updated,
        changed_fields=tuple(changes),
        findings=tuple(findings),
    )
