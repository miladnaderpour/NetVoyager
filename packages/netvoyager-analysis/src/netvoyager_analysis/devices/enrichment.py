"""Read-only legacy hostname enrichment proposal.

Attribute acceptance and provenance belong to AttributeAssertionStore and
an authorized reconciliation workflow; this module never mutates devices.
"""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from .matching import DeviceMatch

EnrichmentStatus = Literal["updated", "unchanged", "conflict", "skipped"]

@dataclass(frozen=True, slots=True)
class DeviceEnrichmentResult:
    device_id: UUID
    field_name: str
    status: EnrichmentStatus
    previous_value: str | None
    observed_value: str | None
    evidence_id: UUID | None = None
    reason: str | None = None

def enrich_device(match: DeviceMatch, *, source: str | None = None,
                  evidence_store: object | None = None, overwrite: bool = False) -> DeviceEnrichmentResult:
    """Report a proposed hostname change; never apply it automatically."""
    previous = match.device.host_name
    observed = match.observation.host_name
    observed = observed.strip() or None if isinstance(observed, str) else None
    if observed is None:
        status: EnrichmentStatus = "skipped"
        reason = "No observed hostname"
    elif previous is not None and previous.strip().casefold() == observed.casefold():
        status = "unchanged"
        reason = None
    elif match.matched_by not in {"serial", "serial_without_leading_zero"}:
        status = "skipped"
        reason = "No strong physical identity"
    else:
        status = "conflict"
        reason = "Hostname requires explicit authorized attribute reconciliation"
    return DeviceEnrichmentResult(match.device.device_id, "host_name", status, previous, observed, reason=reason)
