
"""Shared network scopes with independent device, ASN, and prefix collections.

Scopes describe logical groupings such as regions, sites, buildings, or
network segments. They store direct relationships without discovery evidence
or analysis decisions.

Each scope has a deterministic UUIDv5 identity derived from its name.
Scope state is identified separately using selected scope attributes.
Device, ASN, and prefix associations are excluded from state identity.

Importers provide validated, correctly typed values. These models do not
perform runtime type conversion or validate external input.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar
from uuid import UUID, uuid5

from netvoyager_network.device.models import NetworkDevice
from netvoyager_network.scope.exceptions import (
    DuplicateScopeAsnError,
    DuplicateScopeDeviceError,
    DuplicateScopePrefixError,
)


NETWORK_SCOPE_NAMESPACE = UUID(
    "6b357d96-9b1d-4a73-a1c4-b9c4baf7e622"
)

NETWORK_SCOPE_STATE_NAMESPACE = UUID(
    "c68ac46d-3dde-4f43-ae73-75fe5642e60d"
)


@dataclass(slots=True)
class NetworkScope:
    """A logical grouping with deterministic identity and state.

    The scope_id is generated from the name and remains unchanged
    throughout the object's lifetime.

    The name is an identity field and cannot be modified after
    initialization. Renaming requires establishing a new identity
    under the current naming strategy.

    The state_id is calculated from scope_id and selected scope
    attributes. Changes to these attributes produce a new state UUID
    without changing the scope identity.

    Device, ASN, and prefix associations are managed independently
    and do not participate in scope state identity.

    parent_id references the immediate parent scope by UUID.
    None indicates a root scope.

    Device associations, ASN associations, and prefix assignments are
    independent:
    - Adding a device does not assign its addresses, prefixes, or ASNs.
    - Adding an ASN does not assign that AS's prefixes or devices.
    - Adding a prefix does not establish device or ASN associations.
    - Parent scopes do not automatically receive child associations.

    Collections are managed through methods and exposed as immutable
    membership snapshots. Device objects remain shared and mutable;
    their attributes are not copied or frozen.

    Only direct associations are stored. Descendant aggregation belongs
    to the code managing the scope hierarchy. Device associations do not
    modify NetworkDevice.site or associations held by other scopes.

    The registry is responsible for unique scope IDs, valid parent
    references, cycle prevention, and cross-scope prefix conflicts.

    Device membership uses device_id, not names, addresses, or serials.
    Reconciliation of physical duplicates belongs outside this model.

    Evidence and inference belong in the analysis package.

    Type annotations describe expected values but do not perform
    runtime validation or conversion.
    """

    STATE_FIELDS: ClassVar[tuple[str, ...]] = (
        "kind",
        "parent_id",
        "description",
    )

    name: str

    scope_id: UUID = field(
        init=False,
        compare=True,
    )

    kind: str | None = None
    parent_id: UUID | None = None
    description: str | None = None

    _asns: set[int] = field(
        default_factory=set,
        init=False,
        repr=False,
    )

    _prefix_ids: set[UUID] = field(
        default_factory=set,
        init=False,
        repr=False,
    )

    _devices: dict[UUID, NetworkDevice] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Generate the scope UUIDv5 from its name."""
        object.__setattr__(
            self,
            "scope_id",
            uuid5(
                NETWORK_SCOPE_NAMESPACE,
                f"network-scope:{self.name}",
            ),
        )

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent changes to identity fields after initialization."""
        if name in {"name", "scope_id"} and hasattr(self, name):
            raise AttributeError(
                f"{name} cannot be modified after initialization."
            )

        object.__setattr__(self, name, value)

    @property
    def state_id(self) -> UUID:
        """Return a deterministic UUIDv5 for the current scope state.

        The state includes the scope identity and selected descriptive
        and hierarchy attributes. Each evaluation reflects the current
        field values.

        Device, ASN, and prefix memberships do not participate in
        scope state identity.
        """
        state = {
            field_name: (
                str(value)
                if isinstance(value, UUID)
                else value
            )
            for field_name in self.STATE_FIELDS
            for value in (getattr(self, field_name),)
        }

        payload = json.dumps(
            {
                "schema": "network-scope-state-v1",
                "scope_id": str(self.scope_id),
                "state": state,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return uuid5(
            NETWORK_SCOPE_STATE_NAMESPACE,
            payload,
        )

    def add_asn(self, asn: int) -> None:
        """Associate an ASN directly with this scope.

        Raise DuplicateScopeAsnError if the ASN is already associated.
        A duplicate leaves the collection unchanged.

        This operation stores only the ASN identifier. It does not modify
        an AutonomousSystem object or assign prefixes or devices.
        """
        if asn in self._asns:
            raise DuplicateScopeAsnError(
                scope_id=self.scope_id,
                asn=asn,
            )

        self._asns.add(asn)

    def remove_asn(self, asn: int) -> None:
        """Remove a direct ASN association if it exists.

        A missing ASN leaves the collection unchanged. Device and prefix
        associations, and associations held by other scopes, are unaffected.
        """
        self._asns.discard(asn)

    @property
    def asns(self) -> frozenset[int]:
        """Return an immutable snapshot of directly associated ASNs.

        The snapshot excludes descendant associations and has no defined
        display order. Later changes to the scope do not alter previously
        returned snapshots.
        """
        return frozenset(self._asns)

    def add_prefix(self, prefix_id: UUID) -> None:
        """Associate a network prefix directly with this scope.

        Raise DuplicateScopePrefixError if the prefix ID is already
        associated. A duplicate leaves the collection unchanged.

        This operation does not inspect other scopes, establish device or
        ASN associations, or modify parent and child scopes. Cross-scope
        checks must be performed outside this model.
        """
        if prefix_id in self._prefix_ids:
            raise DuplicateScopePrefixError(
                scope_id=self.scope_id,
                prefix_id=prefix_id,
            )

        self._prefix_ids.add(prefix_id)

    def remove_prefix(self, prefix_id: UUID) -> None:
        """Remove a direct network prefix association if it exists.

        A missing prefix ID leaves the collection unchanged.

        Device and ASN associations, and assignments in other scopes,
        are unaffected.
        """
        self._prefix_ids.discard(prefix_id)

    @property
    def prefix_ids(self) -> frozenset[UUID]:
        """Return an immutable snapshot of associated network prefix IDs.

        The snapshot excludes descendant assignments and has no defined
        display order. Later changes to the scope do not alter previously
        returned snapshots.
        """
        return frozenset(self._prefix_ids)

    def add_device(self, device: NetworkDevice) -> None:
        """Associate a device directly with this scope using its device ID.

        Store the original object reference without copying the device.
        Later attribute changes are visible through this association.

        Raise DuplicateScopeDeviceError if the ID is already present,
        including when a different object has the same ID. The existing
        association is retained without replacement or merging.

        Different IDs remain separate even when device attributes match.
        This operation does not modify device.site, infer ASN or prefix
        associations, or change membership in other scopes.
        """
        if device.device_id in self._devices:
            raise DuplicateScopeDeviceError(
                scope_id=self.scope_id,
                device_id=device.device_id,
            )

        self._devices[device.device_id] = device

    def remove_device(self, device_id: UUID) -> None:
        """Remove a direct device association if it exists.

        A missing ID leaves the collection unchanged. Removing an
        association does not delete or modify the device, affect other
        scopes, or remove ASN and prefix associations.
        """
        self._devices.pop(device_id, None)

    @property
    def devices(self) -> Mapping[UUID, NetworkDevice]:
        """Return a read-only snapshot of direct device membership.

        Keys are device IDs and values are the original device objects.
        The snapshot preserves association insertion order and excludes
        descendant devices.

        Later additions or removals do not change the returned mapping.
        Device objects are shared and remain mutable, so their attribute
        changes are visible through previously returned snapshots.
        """
        return MappingProxyType(self._devices.copy())
