"""Source-reported links expressed using source references, never DB UUIDs."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

RelationshipKind = Literal[
    "location_device", "prefix_device", "prefix_location", "as_device",
    "device_connection", "prefix_as", "interface_prefix", "interface_connection",
]

class ImportRelationship(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    relationship_type: RelationshipKind
    source_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    relation: str | None = None  # e.g. member_of, bgp_peer, connected, originated
    discovery_protocol: Literal["cdp", "lldp"] | None = None
    source_object_id: str | None = None
    source_attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_ref", "target_ref")
    @classmethod
    def nonempty_reference(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("relationship reference must not be blank")
        return value
