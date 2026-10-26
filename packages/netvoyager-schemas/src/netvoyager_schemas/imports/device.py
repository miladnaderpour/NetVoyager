
"""Source-neutral device data reported by an external system.

This is an import contract, not a database Device or a canonical
identity decision.

Observation method describes how information was collected.
It does not establish source trust or identity confidence.
"""

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    field_validator,
)


class ImportDevice(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source_object_id: str | None = None

    observation_method: Literal[
        "direct",
        "neighbor",
        "controller",
        "nms",
    ] = "direct"

    serial: str | None = None
    name: str | None = None
    management_ip: IPvAnyAddress | None = None
    model: str | None = None
    manufacturer: str | None = None

    source_attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "serial",
        "name",
        "source_object_id",
        "model",
        "manufacturer",
    )
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None
