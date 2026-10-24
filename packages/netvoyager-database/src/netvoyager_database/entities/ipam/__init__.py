"""IPAM persistence entities."""

from .prefix_discovery import (
    PrefixObservationEntity,
    PrefixDiscoveryCandidateEntity,
    PrefixCandidateObservationEntity,
)
from .discovery_relationship import PrefixDiscoveryRelationshipEntity
from .discovery_decision import PrefixDiscoveryDecisionEntity

__all__ = [
    "PrefixObservationEntity",
    "PrefixDiscoveryCandidateEntity",
    "PrefixCandidateObservationEntity",
    "PrefixDiscoveryRelationshipEntity",
    "PrefixDiscoveryDecisionEntity",
]