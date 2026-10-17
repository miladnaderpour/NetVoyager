
"""Retrieve evidence associated with resolved network devices.

Combine direct canonical-device evidence with evidence belonging to
discovery candidates that have been resolved to the same device.

Candidate resolution is obtained from DeviceDiscoveryStore.
EvidenceStore remains responsible only for provenance and object links.
"""

from uuid import UUID

from ...evidence.models import EvidenceRecord
from ...evidence.store import EvidenceStore
from .store import DeviceDiscoveryStore


def evidence_for_device(
    device_id: UUID,
    *,
    evidence_store: EvidenceStore,
    discovery_store: DeviceDiscoveryStore,
) -> tuple[EvidenceRecord, ...]:
    """Return complete linked evidence for a canonical network device.

    Include evidence directly linked to the NetworkDevice and evidence
    linked to candidates currently resolved to that device.

    The discovery store determines candidate-to-device associations.
    EvidenceStore performs indexed retrieval using supplied object IDs.

    Repeated evidence records are returned once in original insertion
    order. Original candidate evidence links remain unchanged.

    Candidate relationship decision history is managed separately
    by DeviceDiscoveryStore.
    """
    object_keys: list[tuple[str, UUID | str]] = [
        ("network_device", device_id),
    ]

    candidates = discovery_store.candidates_for_device(
        device_id
    )

    object_keys.extend(
        (
            "device_discovery_candidate",
            candidate.candidate_id,
        )
        for candidate in candidates
    )

    return evidence_store.for_objects(object_keys)
