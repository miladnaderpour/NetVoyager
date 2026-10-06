"""Process device observations into network device records."""

from collections.abc import Iterable, Mapping

from netvoyager_core.logging import get_logger
from netvoyager_network.device import NetworkDevice

from ..evidence.models import EvidenceRecord
from ..evidence.store import EvidenceStore
from .protocols import DeviceObservation


logger = get_logger("netvoyager.analysis.devices.processing")


def process_device_observations(
    observations: Iterable[DeviceObservation],
    *,
    source: str,
    evidence_store: EvidenceStore,
    context: Mapping[str, object] | None = None,
) -> list[NetworkDevice]:
    """Create network devices and record evidence for device observations.

    One evidence record is created for every observation, including
    observations that do not contain enough information to create a device.

    An observation with a nonempty device name creates a NetworkDevice.
    The evidence record is then linked to that device by its UUID.

    Observations without a usable name remain recorded as evidence but do
    not create a NetworkDevice.

    The returned device list preserves observation encounter order.
    No device deduplication or cross-source reconciliation is performed.
    """
    devices: list[NetworkDevice] = []
    observation_count = 0
    unresolved_count = 0

    for observation in observations:
        observation_count += 1

        evidence = EvidenceRecord(
            source=source,
            details={
                "name": observation.name,
                "host_name": observation.host_name,
                "site": observation.site,
                "role": observation.role,
                "primary_IPv4": observation.primary_IPv4,
                "management_ip": observation.management_ip,
                "manufacturer": observation.manufacturer,
                "model": observation.model,
                "serial_number": observation.serial_number,
                "asset_tag": observation.asset_tag,
                "software_version": observation.software_version,
                "status": observation.status,
                "line": observation.line_number,
                "raw_line": observation.raw_line,
                "context": dict(context) if context is not None else {},
            },
        )
        evidence_store.add(evidence)

        if not observation.name:
            unresolved_count += 1

            logger.debug(
                "Unresolved device observation: line=%s | evidence=%s",
                observation.line_number,
                evidence.id,
            )
            continue

        device = NetworkDevice(
            name=observation.name,
            host_name=observation.host_name,
            site=observation.site,
            role=observation.role,
            primary_IPv4=observation.primary_IPv4,
            management_ip=observation.management_ip,
            manufacturer=observation.manufacturer,
            model=observation.model,
            serial_number=observation.serial_number,
            asset_tag=observation.asset_tag,
            software_version=observation.software_version,
            status=observation.status,
        )
        devices.append(device)

        evidence_store.link(
            evidence.id,
            "network_device",
            device.device_id,
        )

        logger.debug(
            "Device created: name=%s | device_id=%s | evidence=%s",
            device.name,
            device.device_id,
            evidence.id,
        )

    logger.info(
        "Device observations processed: observations=%d, devices=%d, "
        "unresolved=%d",
        observation_count,
        len(devices),
        unresolved_count,
    )

    return devices