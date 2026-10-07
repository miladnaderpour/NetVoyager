"""Build baseline site scopes from network devices."""

from collections.abc import Iterable

from netvoyager_core.logging import get_logger
from netvoyager_network.device.models import NetworkDevice
from netvoyager_network.scope.models import NetworkScope


logger = get_logger("netvoyager.analysis.devices.scopes")


def build_site_scopes(
    devices: Iterable[NetworkDevice],
) -> dict[str, NetworkScope]:
    """Create baseline site scopes from device site assignments.

    One NetworkScope is created for each distinct nonempty device site.
    Devices are associated directly with the corresponding site scope.

    Devices without a site remain unassigned and do not create a scope.
    Site names are used as the initial scope IDs because no separate
    canonical site identity has been resolved yet.

    The returned dictionary preserves the encounter order of first-seen
    sites and is keyed by scope ID.

    This function performs no site reconciliation, Panorama validation,
    prefix assignment, ASN assignment, or hierarchy inference.
    """
    scopes: dict[str, NetworkScope] = {}
    device_count = 0
    unassigned_count = 0

    for device in devices:
        device_count += 1

        if not device.site:
            unassigned_count += 1

            logger.debug(
                "Device has no site assignment: name=%s | device_id=%s",
                device.name,
                device.device_id,
            )
            continue

        scope = scopes.get(device.site)

        if scope is None:
            scope = NetworkScope(
                scope_id=device.site,
                name=device.site,
                kind="site",
            )
            scopes[device.site] = scope

            logger.debug(
                "Site scope created: scope_id=%s",
                scope.scope_id,
            )

        scope.add_device(device)

        logger.debug(
            "Device associated with site: device_id=%s | "
            "name=%s | scope_id=%s",
            device.device_id,
            device.name,
            scope.scope_id,
        )

    logger.info(
        "Site scopes built: devices=%d, sites=%d, unassigned=%d",
        device_count,
        len(scopes),
        unassigned_count,
    )

    return scopes