"""Models for IPAM analysis results."""

from dataclasses import dataclass

from netvoyager_network.device.models import NetworkDevice
from netvoyager_network.ipam.models import NetworkPrefix


@dataclass(frozen=True, slots=True)
class SitePrefixAssociation:
    """Association between one canonical network prefix and one site.

    The association is derived from network devices whose management
    addresses match the canonical NetworkPrefix.

    Multiple associations may exist for the same NetworkPrefix when devices
    from different sites match that prefix. Analysis records that condition
    as a Finding.
    """

    site: str
    prefix: NetworkPrefix
    devices: tuple[NetworkDevice, ...]


@dataclass(frozen=True, slots=True)
class SitePrefixAnalysisResult:
    """Result of associating inventory devices with network prefixes."""

    associations: tuple[SitePrefixAssociation, ...]

    @property
    def matched_devices(self) -> tuple[NetworkDevice, ...]:
        """Return all devices participating in prefix associations."""
        devices: dict[
            object,
            NetworkDevice,
        ] = {}

        for association in self.associations:
            for device in association.devices:
                devices[
                    device.device_id
                ] = device

        return tuple(
            devices.values()
        )