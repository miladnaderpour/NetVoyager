"""Unresolved network neighbor observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class NeighborObservation:
    """Describe an advertised neighbor without resolving its identity."""

    local_device_ref: str
    local_interface: str
    protocol: str

    remote_device_name: str | None = None
    remote_interface: str | None = None
    remote_management_ip: str | None = None
    remote_platform: str | None = None

    observation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.local_device_ref.strip():
            raise ValueError("Neighbor requires a local device reference")
        if not self.local_interface.strip():
            raise ValueError("Neighbor requires a local interface")
        if not self.protocol.strip():
            raise ValueError("Neighbor requires a discovery protocol")