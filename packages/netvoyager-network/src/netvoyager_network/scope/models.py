"""Shared network scopes with independent ASN and prefix collections.

Scopes describe logical groupings such as regions, sites, buildings, or
network segments. They store direct relationships without discovery evidence
or analysis decisions.

Importers provide validated, correctly typed values. These models do not
perform runtime type conversion or validate external input.
"""

from dataclasses import dataclass, field
from ipaddress import IPv4Network

from netvoyager_network.scope.exceptions import (
    DuplicateScopeAsnError,
    DuplicateScopePrefixError,
)


@dataclass(slots=True)
class NetworkScope:
    """A logical network grouping with direct ASN and prefix associations.

    scope_id identifies the scope independently of its display name.
    parent_id references its immediate parent; None indicates a root scope.
    kind optionally describes the grouping, such as "region" or "site".

    AS associations and prefix assignments are independent:
    - Adding an ASN does not assign that AS's prefixes.
    - Adding a prefix does not establish an AS association.
    - Parent scopes do not automatically receive child associations.

    Collections are managed through methods and exposed as immutable
    snapshots. Only direct associations are stored; descendant aggregation
    belongs to the code managing the scope hierarchy.

    The registry is responsible for unique scope IDs, valid parent
    references, cycle prevention, and cross-scope prefix conflicts.
    Treat scope_id as stable once the scope has been registered.

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
    _prefixes: set[IPv4Network] = field(
        default_factory=set,
        init=False,
        repr=False,
    )

    def add_asn(self, asn: int) -> None:
        """Associate an ASN directly with this scope.

        Raise DuplicateScopeAsnError if the ASN is already associated.
        A duplicate leaves the collection unchanged.

        This operation stores only the ASN identifier. It does not modify
        an AutonomousSystem object or assign any prefixes to the scope.
        """
        if asn in self._asns:
            raise DuplicateScopeAsnError(
                scope_id=self.scope_id,
                asn=asn,
            )

        self._asns.add(asn)

    def remove_asn(self, asn: int) -> None:
        """Remove a direct ASN association if it exists.

        A missing ASN leaves the collection unchanged. Prefix assignments
        and associations held by other scopes are unaffected.
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

    def add_prefix(self, prefix: IPv4Network) -> None:
        """Assign an IPv4 prefix directly to this scope.

        Raise DuplicateScopePrefixError if the exact prefix already exists.
        Overlapping prefixes are distinct and are not rejected here.

        This operation does not inspect other scopes, establish an ASN
        association, or modify parent and child scopes. Cross-scope checks
        must be performed by the registry before calling this method.
        """
        if prefix in self._prefixes:
            raise DuplicateScopePrefixError(
                scope_id=self.scope_id,
                prefix=prefix,
            )

        self._prefixes.add(prefix)

    def remove_prefix(self, prefix: IPv4Network) -> None:
        """Remove an exact direct prefix assignment if it exists.

        A missing prefix leaves the collection unchanged. Removing a
        supernet does not remove more-specific prefixes, and removing
        a subnet does not affect a containing network.

        ASN associations and assignments in other scopes are unaffected.
        """
        self._prefixes.discard(prefix)

    @property
    def prefixes(self) -> frozenset[IPv4Network]:
        """Return an immutable snapshot of directly assigned prefixes.

        The snapshot excludes descendant assignments and does not aggregate
        or collapse networks. Callers can sort it for reports or exports.

        Later changes to the scope do not alter previously returned
        snapshots.
        """
        return frozenset(self._prefixes)