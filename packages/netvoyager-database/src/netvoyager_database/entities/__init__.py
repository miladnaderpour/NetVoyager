
"""Register SQLAlchemy entities for schema initialization."""

from .devices import (
    DeviceDiscoveryCandidateEntity,
    DeviceDiscoveryRelationshipEntity,
    NetworkDeviceEntity,
)

__all__ = [
    "DeviceDiscoveryCandidateEntity",
    "DeviceDiscoveryRelationshipEntity",
    "NetworkDeviceEntity",
]
