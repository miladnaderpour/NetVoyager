# netwoyager-network/netvoyager_network/bgp/models.py
"""Shared BGP domain models for prefix observations and autonomous systems.

Importers are responsible for parsing and validating external values before
constructing these models. Type annotations describe the expected Python
types; they do not perform runtime conversion or validation.
"""

from uuid import UUID, uuid4
from dataclasses import dataclass, field
from ipaddress import IPv4Network, IPv4Address

from netvoyager_network.bgp.exceptions import DuplicatePrefixError


@dataclass(frozen=True, slots=True)
class AsPrefix:
    """An observed IPv4 prefix associated with an origin ASN.

    The ASN identifies the attributed origin of the prefix. The optional
    AS path preserves the sequence provided by the observation source:
    - None means the path was unavailable or not collected.
    - An empty tuple means an empty path was observed.
    - A populated tuple contains the observed ASN sequence.

    Repeated ASNs are preserved because they may represent AS prepending.
    The model does not derive or verify the origin ASN from the path.

    Equality compares ASN, prefix, and AS path, excluding the ID.
    Identical observations can therefore compare equal while retaining
    separate IDs.
    """

    id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
        compare=False,
    )
    asn: int
    prefix: IPv4Network
    as_path: tuple[int, ...] | None = None

    def contains(self, address: IPv4Address) -> bool:
        """Return whether the IPv4 address belongs to this prefix.

        This checks membership in this individual network. It does not compare
        other prefixes or determine whether this is the most specific match.
        """
        return address in self.prefix


@dataclass(slots=True)
class AutonomousSystem:
    """An autonomous system with a mutable collection of unique IPv4 prefixes.

    Prefixes are managed through add_prefix() and remove_prefix(). The
    prefixes property exposes an immutable snapshot for other packages
    to inspect without modifying the internal collection.

    Uniqueness is based on exact network equality. Overlapping networks
    remain separate entries, and the same prefix may exist in another AS.

    AS paths belong to individual observations and are not stored here.
    An association with this model does not establish exclusive ownership
    of a prefix or prove that the route is currently active.

    The UUID identifies this object for evidence links. Preserve it when
    saving and restoring the object, and do not reassign it. Equality
    compares the ASN and prefix collection, excluding the ID.
    """

    id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
        compare=False,
    )
    asn: int
    _prefixes: set[IPv4Network] = field(
        default_factory=set,
        init=False,
        repr=False,
    )

    def add_prefix(self, prefix: IPv4Network) -> None:
        """Associate an IPv4 prefix with this autonomous system.

        Raise DuplicatePrefixError if the exact prefix already exists.
        On a duplicate, the existing collection remains unchanged.

        The caller decides whether a duplicate should stop processing,
        be reported, or be ignored during an import.
        """
        if prefix in self._prefixes:
            raise DuplicatePrefixError(asn=self.asn, prefix=prefix)

        self._prefixes.add(prefix)

    def remove_prefix(self, prefix: IPv4Network) -> None:
        """Remove an exact prefix association if it exists.

        A missing prefix leaves the collection unchanged. Removing a
        supernet does not remove its more-specific prefixes, and removing
        a subnet does not affect any containing network.
        """
        self._prefixes.discard(prefix)

    @property
    def prefixes(self) -> frozenset[IPv4Network]:
        """Return an immutable snapshot of the current prefix collection.

        Later additions or removals do not change previously returned
        snapshots. The collection has no defined display order; callers
        can sort it when producing reports or exports.
        """
        return frozenset(self._prefixes)

@dataclass(slots=True)
class AsGroupingResult:
    """Autonomous systems and repeated prefixes from AsPrefix records.

    autonomous_systems maps each ASN to an AutonomousSystem containing
    its unique IPv4 prefixes.

    duplicates maps every prefix appearing more than once to all its
    input records, including the first occurrence. Records may contain
    the same ASN or different ASNs and preserve their encounter order.

    Duplicate membership reports repetition without deciding whether
    the input is valid or conflicting.
    """

    autonomous_systems: dict[int, AutonomousSystem] = field(
        default_factory=dict
    )
    duplicates: dict[IPv4Network, tuple[AsPrefix, ...]] = field(
        default_factory=dict
    )

@dataclass(slots=True)
class AsPrefixMatchResult:
    """Best prefix matches and the outcome of a prefix-length check.

    matches contains all retained AsPrefix records at the longest prefix
    containing the requested address. Records preserve input encounter
    order, duplicate occurrences, ASNs, and AS paths.

    matched_prefix_length records the best prefix length found before
    applying the minimum-length policy. None means no prefix matched.

    is_broader_than_expected indicates that the best matching prefix
    was shorter than the requested minimum. It is False when no minimum
    was supplied or no prefix matched.

    In flag mode, broad matches remain in matches. In skip mode, matches
    is empty, but matched_prefix_length and is_broader_than_expected
    retain the assessment of the skipped matches.

    The result does not select an ASN or resolve ambiguous associations.
    """

    matches: tuple[AsPrefix, ...] = field(default_factory=tuple)
    matched_prefix_length: int | None = None
    is_broader_than_expected: bool = False