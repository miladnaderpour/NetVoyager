
"""Source-specific network prefix observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Network, IPv6Network
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class PrefixObservation:
    """Report a source-observed network without asserting canonical identity.

    ``address_space_id=None`` means unresolved, not the global space.
    Source identity and collection time belong to the containing SourceDataset.
    """

    local_ref: str
    prefix: IPv4Network | IPv6Network
    observation_kind: str
    routing_context: str | None = None
    address_space_id: UUID | None = None
    local_device_ref: str | None = None
    observation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not isinstance(self.local_ref, str) or not self.local_ref.strip():
            raise ValueError("Prefix observation requires a local reference")
        if not isinstance(self.prefix, (IPv4Network, IPv6Network)):
            raise TypeError(
                "Prefix observation requires an IPv4Network or IPv6Network"
            )
        if not isinstance(self.observation_kind, str) or not self.observation_kind.strip():
            raise ValueError("Prefix observation requires an observation kind")
        if self.address_space_id is not None and not isinstance(self.address_space_id, UUID):
            raise TypeError("address_space_id must be a UUID or None")
        if self.routing_context is not None and not isinstance(self.routing_context, str):
            raise TypeError("routing_context must be a string or None")
        if self.local_device_ref is not None and (
            not isinstance(self.local_device_ref, str) or not self.local_device_ref.strip()
        ):
            raise ValueError("local_device_ref must be a nonempty string or None")
