"""Source-reported location information and optional parent reference."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class ImportLocation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_object_id: str | None = None
    code: str | None = None
    name: str | None = None
    location_type: str | None = None
    description: str | None = None
    parent_ref: str | None = None
    source_attributes: dict[str, Any] = Field(default_factory=dict)
