
"""SQLAlchemy entities for network-device persistence."""

from .discovery_candidate import DeviceDiscoveryCandidateEntity
from .discovery_relationship import DeviceDiscoveryRelationshipEntity
from .network_device import NetworkDeviceEntity

__all__ = [
    "DeviceDiscoveryCandidateEntity",
    "DeviceDiscoveryRelationshipEntity",
    "NetworkDeviceEntity",
]
