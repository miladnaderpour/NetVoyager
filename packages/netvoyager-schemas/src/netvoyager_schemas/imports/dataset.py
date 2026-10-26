"""A source-neutral batch of reported entities and relationships.

Field defaults maintain compatibility with the original device-only SourceDataset.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from .device import ImportDevice
from .interface import ImportInterface
from .network_prefix import ImportNetworkPrefix
from .autonomous_system import ImportAutonomousSystem
from .location import ImportLocation
from .relationship import ImportRelationship

class SourceDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_id: str
    collected_at: datetime
    devices: tuple[ImportDevice, ...] = ()
    interfaces: tuple[ImportInterface, ...] = ()
    prefixes: tuple[ImportNetworkPrefix, ...] = ()
    autonomous_systems: tuple[ImportAutonomousSystem, ...] = ()
    locations: tuple[ImportLocation, ...] = ()
    relationships: tuple[ImportRelationship, ...] = ()

    @field_validator("source_id")
    @classmethod
    def nonempty_source_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source_id must not be blank")
        return value

    @field_validator("collected_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        return value
