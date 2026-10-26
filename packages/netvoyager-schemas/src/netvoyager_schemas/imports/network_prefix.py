"""Source-reported prefix; CIDR is validated, not canonicalized."""
from ipaddress import ip_network
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ImportNetworkPrefix(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_object_id: str | None = None
    cidr: str
    address_space: str | None = None
    vrf: str | None = None
    vlan: int | None = Field(default=None, ge=1, le=4094)
    description: str | None = None
    status: str | None = None
    source_attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str) -> str:
        value = value.strip()
        try:
            ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError("invalid IPv4 or IPv6 CIDR") from exc
        return value
