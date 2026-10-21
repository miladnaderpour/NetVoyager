
"""Source identity and normalized collection datasets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from netvoyager_analysis.devices.observations import DeviceObservation
    from netvoyager_analysis.neighbors.observations import NeighborObservation
    from netvoyager_analysis.ipam.observations import PrefixObservation


@dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """Identify an origin of collected network information."""

    name: str
    source_type: str
    source_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Source name cannot be empty")
        if not self.source_type.strip():
            raise ValueError("Source type cannot be empty")


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceDataset:
    """Normalized observations produced by one import or collection."""

    source: Source
    devices: tuple[DeviceObservation, ...] = ()
    neighbors: tuple[NeighborObservation, ...] = ()
    network_prefixes: tuple[PrefixObservation, ...] = ()
    collected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    dataset_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.collected_at.tzinfo is None:
            raise ValueError("collected_at must be timezone-aware")
