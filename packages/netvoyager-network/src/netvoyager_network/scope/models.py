"""Shared network scopes with independent device, ASN, and prefix collections.

Scopes describe logical groupings such as regions, sites, buildings, or
network segments. They store direct relationships without discovery evidence
or analysis decisions.

Importers provide validated, correctly typed values. These models do not
perform runtime type conversion or validate external input.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from ipaddress import IPv4Network
from types import MappingProxyType
from uuid import UUID

from netvoyager_network.device.models import NetworkDevice
from netvoyager_network.scope.exceptions import (
    DuplicateScopeAsnError,
    DuplicateScopeDeviceError,
    DuplicateScopePrefixError,
)

@dataclass(slots=True)
class NetworkScope:
    """A logical grouping with direct device, ASN, and prefix associations.

    scope_id identifies the scope independently of its display name.
    parent_id references its immediate parent; None indicates a root scope.
    kind optionally describes the grouping, such as "region" or "site".

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
    Treat scope_id and associated device IDs as stable.

    Device membership uses device_id, not names, addresses, or serials.
    Reconciliation of physical duplicates belongs outside this model.

    This first version does not distinguish identical prefixes in different
    routing contexts. Evidence and inference belong in the analysis package.
    """

    scope_id: str
    name: str
    kind: str | None = None
    parent_id: str | None = None
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
        The caller must not change device.device_id after association.

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