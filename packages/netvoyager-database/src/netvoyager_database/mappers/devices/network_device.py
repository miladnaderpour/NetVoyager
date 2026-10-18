
"""Conversion between canonical network devices and SQLAlchemy entities."""

from ipaddress import IPv4Address

from netvoyager_core.exceptions import NetVoyagerInvariantError
from netvoyager_network.device.models import NetworkDevice

from netvoyager_database.entities.devices import NetworkDeviceEntity

def to_entity(device: NetworkDevice) -> NetworkDeviceEntity:
    """Create a persistence entity from a canonical network device."""
    return NetworkDeviceEntity(
        device_id=device.device_id,
        name=device.name,
        role=device.role,
        site=device.site,
        description=device.description,
        primary_ipv4=(
            str(device.primary_IPv4)
            if device.primary_IPv4 is not None
            else None
        ),
        management_ip=(
            str(device.management_ip)
            if device.management_ip is not None
            else None
        ),
        host_name=device.host_name,
        virtual_chassis=device.virtual_chassis,
        manufacturer=device.manufacturer,
        model=device.model,
        serial_number=device.serial_number,
        status=device.status,
        asset_tag=device.asset_tag,
        software_version=device.software_version,
        integration_metadata=device.metadata,
    )


def to_domain(entity: NetworkDeviceEntity) -> NetworkDevice:
    """Reconstruct and verify a canonical network device from storage.

    Domain identity is recalculated using the established UUIDv5
    contract. An inconsistent stored identifier is rejected.
    """
    device = NetworkDevice(
        name=entity.name,
        role=entity.role,
        site=entity.site,
        description=entity.description,
        primary_IPv4=(
            IPv4Address(entity.primary_ipv4)
            if entity.primary_ipv4 is not None
            else None
        ),
        management_ip=(
            IPv4Address(entity.management_ip)
            if entity.management_ip is not None
            else None
        ),
        host_name=entity.host_name,
        virtual_chassis=entity.virtual_chassis,
        manufacturer=entity.manufacturer,
        model=entity.model,
        serial_number=entity.serial_number,
        status=entity.status,
        asset_tag=entity.asset_tag,
        software_version=entity.software_version,
    )

    if device.device_id != entity.device_id:
        raise NetVoyagerInvariantError(
            code="database.device_identity_mismatch",
            message="Stored device identity does not match its canonical name.",
            details={
                "stored_device_id": str(entity.device_id),
                "expected_device_id": str(device.device_id),
                "name": entity.name,
            },
        )

    for namespace, values in (entity.integration_metadata or {}).items():
        device.update_metadata(namespace, values)

    return device
