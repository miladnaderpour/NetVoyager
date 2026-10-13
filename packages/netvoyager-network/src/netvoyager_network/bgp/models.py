# netwoyager-network/netvoyager_network/bgp/models.py
"""Shared BGP domain models for prefix observations and autonomous systems.

Importers are responsible for parsing and validating external values before
constructing these models. Type annotations describe the expected Python
types; they do not perform runtime conversion or validation.
"""

from uuid import UUID, uuid4,uuid5
from dataclasses import dataclass, field
from typing import Literal
from ipaddress import IPv4Network, IPv4Address

from netvoyager_network.bgp.exceptions import DuplicatePrefixError

AS_PREFIX_NAMESPACE = UUID("a3e41b7d-29f0-4b6c-8d15-7f0e2a96c531")

AUTONOMOUS_SYSTEM_NAMESPACE = UUID(
    "e72a1354-813e-4d68-bd28-e7f0ab655b20"
)


@dataclass(frozen=True, slots=True)
class AsPrefix:
    """An IPv4 BGP prefix observation reported by a network device.

    Identity is derived from the reporting device UUID, normalized
    prefix, and attributed origin ASN.

    AS path and BGP ORIGIN are observation attributes and do not
    participate in identity generation.

    Identical identity fields produce the same UUID across runs.
    """

    source_id: UUID
    asn: int
    prefix: IPv4Network
    as_path: tuple[int, ...] | None = None
    origin: Literal["igp", "egp", "incomplete"] | None = None

    id: UUID = field(init=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "id",
            uuid5(
                AS_PREFIX_NAMESPACE,
                f"as-prefix:{self.source_id}:"
                f"{self.prefix.with_prefixlen}:{self.asn}",
            ),
        )

    def contains(self, address: IPv4Address) -> bool:
        """Return whether the IPv4 address belongs to this prefix."""
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
    init=False,
    compare=False,
    )

    asn: int
    _prefixes: set[IPv4Network] = field(
        default_factory=set,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Generate deterministic identity from the autonomous system number."""
        object.__setattr__(
            self,
            "id",
            uuid5(
                AUTONOMOUS_SYSTEM_NAMESPACE,
                f"autonomous-system:{self.asn}",
            ),
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