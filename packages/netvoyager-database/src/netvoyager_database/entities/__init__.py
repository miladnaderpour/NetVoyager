
"""Register SQLAlchemy entities for schema initialization."""

from .devices import (
    DeviceDiscoveryCandidateEntity,
    DeviceDiscoveryDecisionEntity,
    DeviceDiscoveryRelationshipEntity,
    NetworkDeviceEntity,
)

from .ipam import (
    PrefixCandidateObservationEntity,
    PrefixDiscoveryCandidateEntity,
    PrefixObservationEntity,
    PrefixDiscoveryDecisionEntity,
    PrefixDiscoveryRelationshipEntity,
)

__all__ = [
    "DeviceDiscoveryCandidateEntity",
    "DeviceDiscoveryDecisionEntity",
    "DeviceDiscoveryRelationshipEntity",
    "NetworkDeviceEntity",
    "PrefixCandidateObservationEntity",
    "PrefixDiscoveryCandidateEntity",
    "PrefixObservationEntity",
    "PrefixDiscoveryDecisionEntity",
    "PrefixDiscoveryRelationshipEntity",
]
