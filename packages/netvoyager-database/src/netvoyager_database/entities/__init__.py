
"""Register SQLAlchemy entities for schema initialization."""

from .devices import (
    DeviceDiscoveryCandidateEntity,
    DeviceDiscoveryDecisionEntity,
    DeviceDiscoveryRelationshipEntity,
    NetworkDeviceEntity,
)

__all__ = [
    "DeviceDiscoveryCandidateEntity",
    "DeviceDiscoveryDecisionEntity",
    "DeviceDiscoveryRelationshipEntity",
    "NetworkDeviceEntity",
]
