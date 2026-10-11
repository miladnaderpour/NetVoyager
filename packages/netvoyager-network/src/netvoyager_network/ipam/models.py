"""Shared IPAM domain models for IPv4 network prefixes.

Importers are responsible for parsing and validating external values before
constructing these models. Type annotations describe the expected Python
types; they do not perform runtime conversion or validation.
"""

from dataclasses import dataclass, field
from ipaddress import IPv4Network
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class NetworkPrefix:
    """A canonical IPv4 network prefix independent of its observation source.

    The prefix represents an IPv4 network that may be discovered through
    BGP, firewall configurations, or other inventory sources.

    The model does not establish site ownership, routing context, or ASN
    association. These relationships are managed by other components.

    Equality and hashing are based on the object's UUID. Identical networks
    can therefore remain distinct objects in different routing contexts.
    """

    id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
    )
    prefix: IPv4Network = field(
        compare=False
    )


@dataclass(frozen=True, slots=True)
class NetworkPrefixMatchResult:
    """Best canonical prefix match for an IPv4 address.

    match contains the most-specific NetworkPrefix containing the requested
    address. None means that no supplied prefix matched.

    matched_prefix_length records the best prefix length found before
    applying the minimum-length policy. None means no prefix matched.

    is_broader_than_expected indicates that the best matching prefix was
    shorter than the requested minimum.

    When broad matches are skipped, match is None while
    matched_prefix_length and is_broader_than_expected preserve information
    about the rejected match.
    """

    match: NetworkPrefix | None = None
    matched_prefix_length: int | None = None
    is_broader_than_expected: bool = False