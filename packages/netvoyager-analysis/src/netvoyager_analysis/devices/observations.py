"""Device identity observations produced by network sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class DeviceObservation:
    """Report device identity without asserting canonical identity."""

    local_ref: str
    hostname: str | None = None
    inventory_name: str | None = None
    serial_number: str | None = None
    management_ip: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    software_version: str | None = None

    observation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.local_ref.strip():
            raise ValueError("Device observation requires a local reference")