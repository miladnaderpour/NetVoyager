"""Reusable eligibility policy for site-prefix correlation."""

from ipaddress import IPv4Network
from typing import Literal


SitePrefixDecision = Literal[
    "ignored",
    "candidate",
    "eligible",
]


def classify_site_prefix(
    prefix: IPv4Network,
    *,
    source: Literal["connected", "static", "bgp"],
    min_prefix_length: int = 13,
    connected_auto_prefix_length: int = 20,
    max_prefix_length: int = 31,
) -> SitePrefixDecision:
    """Classify a prefix for site correlation, without assigning ownership."""
    length = prefix.prefixlen

    if length < min_prefix_length or length > max_prefix_length:
        return "ignored"

    if source == "connected" and length >= connected_auto_prefix_length:
        return "eligible"

    return "candidate"