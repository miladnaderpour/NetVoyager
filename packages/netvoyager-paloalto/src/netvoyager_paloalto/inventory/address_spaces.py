
"""Panorama virtual-router AddressSpace mapping.

The Palo Alto integration owns the mapping. NetVoyager analysis and
diagnostic scripts receive already-resolved AddressSpace identities.

Mappings apply globally by virtual-router name for V1.
Unmapped virtual routers have an unknown AddressSpace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from netvoyager_network.ipam.address_space import GLOBAL_ADDRESS_SPACE


DEFAULT_VIRTUAL_ROUTER_MAPPINGS: Mapping[str, UUID] = MappingProxyType(
    {
        "vpn_intern": GLOBAL_ADDRESS_SPACE.id,
    }
)


@dataclass(frozen=True, slots=True)
class PanoramaAddressSpaces:
    """Resolve Panorama routing contexts to canonical AddressSpace IDs."""

    virtual_routers: Mapping[str, UUID] = field(
        default_factory=lambda: DEFAULT_VIRTUAL_ROUTER_MAPPINGS
    )

    def __post_init__(self) -> None:
        resolved: dict[str, UUID] = {}

        for name, address_space_id in self.virtual_routers.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Virtual-router name must be nonempty")

            if not isinstance(address_space_id, UUID):
                raise TypeError(
                    "Mapped AddressSpace identity must be a UUID"
                )

            if name in resolved:
                raise ValueError(f"Duplicate virtual router: {name}")

            resolved[name] = address_space_id

        object.__setattr__(
            self,
            "virtual_routers",
            MappingProxyType(resolved),
        )

    def resolve(self, virtual_router: str | None) -> UUID | None:
        """Resolve a virtual router without assuming the global space."""
        if virtual_router is None:
            return None

        return self.virtual_routers.get(virtual_router)


DEFAULT_PANORAMA_ADDRESS_SPACES = PanoramaAddressSpaces()
