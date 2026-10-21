
"""Address-space identity independent of routing and management systems."""

from dataclasses import dataclass
from uuid import UUID, uuid5

ADDRESS_SPACE_NAMESPACE = UUID(
    "a2ff2ef8-7277-4d19-9154-a36d97821fc9"
)

GLOBAL_ADDRESS_SPACE_ID = uuid5(
    ADDRESS_SPACE_NAMESPACE,
    "address-space:global",
)


@dataclass(frozen=True, slots=True)
class AddressSpace:
    """An independently identified IP namespace.

    IDs are assigned when a space is established; renaming it does not
    change the ID. Registry-wide name uniqueness belongs to persistence.
    """

    id: UUID
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("AddressSpace.id must be a UUID")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("AddressSpace.name must be nonempty")


GLOBAL_ADDRESS_SPACE = AddressSpace(
    id=GLOBAL_ADDRESS_SPACE_ID,
    name="global",
)
