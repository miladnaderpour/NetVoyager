"""Shared IPAM domain models for IPv4 network prefixes.

Importers are responsible for parsing and validating external values before
constructing these models. Type annotations describe the expected Python
types; they do not perform runtime conversion or validation.
"""

from dataclasses import dataclass, field
from ipaddress import IPv4Network
from uuid import UUID, uuid5

NETWORK_PREFIX_NAMESPACE = UUID(
    "b9a7da8a-5b4f-4f05-8a71-163056b8d682"
)



@dataclass(frozen=True, slots=True)
class NetworkPrefix:
    """A canonical IPv4 network prefix independent of its observation source.

    Identity is deterministically generated from the normalized IPv4 prefix.

    Site ownership, routing context, and ASN associations are managed
    separately.
    """

    prefix: IPv4Network = field(compare=False)

    id: UUID = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "id",
            uuid5(
                NETWORK_PREFIX_NAMESPACE,
                f"network-prefix:{self.prefix.with_prefixlen}",
            ),
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