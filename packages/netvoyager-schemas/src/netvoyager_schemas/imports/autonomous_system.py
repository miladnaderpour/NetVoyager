"""Source-reported autonomous-system data."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class ImportAutonomousSystem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_object_id: str | None = None
    asn: int = Field(ge=0, le=4294967295)
    name: str | None = None
    source_attributes: dict[str, Any] = Field(default_factory=dict)
