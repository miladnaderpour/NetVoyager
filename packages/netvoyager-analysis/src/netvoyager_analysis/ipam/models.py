"""Models for IPAM analysis results."""

from dataclasses import dataclass

from netvoyager_network.bgp.models import AsPrefix
from netvoyager_network.device.models import NetworkDevice


@dataclass(frozen=True, slots=True)
class SitePrefixAssociation:
    """Association between one BGP prefix and one inventory site.

    The association is derived from network devices whose management
    addresses matched the prefix.

    Multiple associations may exist for the same prefix when devices
    from different sites match that prefix. Analysis will record that
    condition as a Finding.
    """

    site: str
    prefix: AsPrefix
    devices: tuple[NetworkDevice, ...]


@dataclass(frozen=True, slots=True)
class SitePrefixAnalysisResult:
    """Result of associating inventory devices with BGP prefixes."""

    associations: tuple[SitePrefixAssociation, ...]

    @property
    def matched_devices(self) -> tuple[NetworkDevice, ...]:
        """Return all devices participating in prefix associations."""
        devices: dict[object, NetworkDevice] = {}

        for association in self.associations:
            for device in association.devices:
                devices[device.device_id] = device

        return tuple(devices.values())