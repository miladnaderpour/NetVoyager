"""Retrieve evidence associated with resolved network devices.

Combine direct canonical-device evidence with evidence belonging to
discovery candidates that have been resolved to the same device.

Evidence is retrieved through the repository protocol.
Candidate resolution is provided by the discovery registry.
"""

from uuid import UUID

from netvoyager_intelligence.evidence import EvidenceRecord
from netvoyager_network.device.discovery.store import DeviceDiscoveryStore

from netvoyager_analysis.protocols.evidence import (
    EvidenceRepositoryProtocol,
)


def evidence_for_device(
    device_id: UUID,
    *,
    evidence_store: EvidenceRepositoryProtocol,
    discovery_store: DeviceDiscoveryStore,
) -> tuple[EvidenceRecord, ...]:
    """Return evidence linked to a device and its resolved candidates."""

    candidate_ids = (
        candidate.candidate_id
        for candidate in discovery_store.candidates_for_device(device_id)
    )

    return evidence_store.for_objects(
        (device_id, *candidate_ids)
    )