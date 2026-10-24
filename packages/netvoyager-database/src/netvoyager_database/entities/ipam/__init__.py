"""IPAM persistence entities."""

from .prefix_discovery import (
    PrefixObservationEntity,
    PrefixDiscoveryCandidateEntity,
    PrefixCandidateObservationEntity,
)
from .discovery_relationship import PrefixDiscoveryRelationshipEntity
from .discovery_decision import PrefixDiscoveryDecisionEntity
from .canonical import AddressSpaceEntity, NetworkPrefixEntity

__all__ = [
    "PrefixObservationEntity",
    "PrefixDiscoveryCandidateEntity",
    "PrefixCandidateObservationEntity",
    "PrefixDiscoveryRelationshipEntity",
    "PrefixDiscoveryDecisionEntity",
    "AddressSpaceEntity",
    "NetworkPrefixEntity",
]