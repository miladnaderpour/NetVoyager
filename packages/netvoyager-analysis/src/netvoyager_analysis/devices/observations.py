"""Device observations produced by inventory and network sources.

Observations report source information without establishing canonical
device identity or authorizing changes to canonical attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class DeviceObservation:
    """Report device identity and inventory attributes from a source.

    A DeviceObservation is independent of a canonical NetworkDevice.

    Missing attributes remain None. Reconciliation and source policies
    determine which reported values may update canonical inventory.
    """

    # Source-local identity
    local_ref: str

    # Device identifiers
    hostname: str | None = None
    inventory_name: str | None = None
    serial_number: str | None = None
    asset_tag: str | None = None

    # Network addressing
    management_ip: str | None = None
    primary_ipv4: str | None = None

    # Device classification
    manufacturer: str | None = None
    model: str | None = None
    software_version: str | None = None
    role: str | None = None

    # Inventory location and lifecycle
    site: str | None = None
    status: str | None = None
    validation_status: str | None = None

    # Independent observation identity
    observation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.local_ref, str) or not self.local_ref.strip():
            raise ValueError(
                "Device observation requires a local reference"
            )