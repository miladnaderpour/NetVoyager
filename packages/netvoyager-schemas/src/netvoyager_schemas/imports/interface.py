"""Interface facts from a source; device_ref refers to a source-local device."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ImportInterface(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_object_id: str | None = None
    device_ref: str | None = None
    name: str = Field(min_length=1)
    mac_address: str | None = None
    interface_type: str | None = None
    description: str | None = None
    operational_status: str | None = None
    source_attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("interface name must not be blank")
        return value
