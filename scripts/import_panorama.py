
"""Import Panorama exports into normalized NetVoyager SourceDatasets.

AddressSpace mapping is passed directly to the Palo Alto parser.
This script does not persist data or perform canonical reconciliation.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid5

import yaml

from netvoyager_analysis.devices.observations import DeviceObservation
from netvoyager_analysis.ipam.observations import PrefixObservation
from netvoyager_analysis.paloalto.subnets import (
    iter_site_subnet_candidates,
)
from netvoyager_analysis.sources.models import Source, SourceDataset
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_network.ipam.address_space import GLOBAL_ADDRESS_SPACE
from netvoyager_paloalto.inventory.parser import (
    parse_panorama_inventory,
)


logger = get_logger("scripts.import_panorama")


def load_address_space_mapping(
    path: Path | None,
) -> dict[str, UUID]:
    """Load an explicit VR-to-AddressSpace mapping.

    Without a configuration file, no virtual router is mapped.
    """
    if path is None:
        return {}

    document = yaml.safe_load(path.read_text(encoding="utf-8-sig"))

    if not isinstance(document, dict):
        raise ValueError("AddressSpace configuration must be a mapping")

    entries = document.get("address_spaces")

    if not isinstance(entries, dict):
        raise ValueError(
            "AddressSpace configuration requires 'address_spaces'"
        )

    known_spaces = {
        GLOBAL_ADDRESS_SPACE.name: GLOBAL_ADDRESS_SPACE.id,
    }

    mapping: dict[str, UUID] = {}

    for virtual_router, space_name in entries.items():
        if not isinstance(virtual_router, str) or not virtual_router.strip():
            raise ValueError("Virtual-router name must be nonempty")

        if not isinstance(space_name, str):
            raise ValueError(
                f"Invalid AddressSpace for virtual router {virtual_router!r}"
            )

        address_space_id = known_spaces.get(space_name)

        if address_space_id is None:
            raise ValueError(
                f"Unknown AddressSpace {space_name!r} "
                f"for virtual router {virtual_router!r}"
            )

        mapping[virtual_router] = address_space_id

    return mapping


def import_panorama(
    path: Path,
    *,
    address_space_mapping: Mapping[str, UUID] | None = None,
) -> tuple[SourceDataset, Counter[str]]:
    """Normalize one Panorama export with optional explicit VR mapping."""
    result = parse_panorama_inventory(
        path.read_text(encoding="utf-8-sig"),
        address_space_mapping=address_space_mapping,
    )

    source = Source(
        name="paloalto_panorama",
        source_type="managed_device_inventory",
        source_id=uuid5(
            NAMESPACE_URL,
            f"netvoyager:source:panorama:{result.panorama}",
        ),
    )

    devices: list[DeviceObservation] = []
    prefixes: list[PrefixObservation] = []
    counts: Counter[str] = Counter()

    counts["firewalls"] = len(result.firewalls)
    counts["parser_issues"] = len(result.issues)
    counts["collection_failures"] = len(result.collection_failures)

    for index, firewall in enumerate(result.firewalls):
        local_ref = f"firewall:{index}:{firewall.serial}"

        management_ip = (
            str(firewall.management.ip_address)
            if (
                firewall.management is not None
                and firewall.management.ip_address is not None
            )
            else None
        )

        devices.append(
            DeviceObservation(
                local_ref=local_ref,
                hostname=firewall.hostname,
                inventory_name=firewall.hostname,
                serial_number=firewall.serial,
                management_ip=management_ip,
                manufacturer="Palo Alto Networks",
            )
        )

        logger.debug(
            "Panorama firewall normalized",
            extra={
                "source_file": str(path),
                "firewall_serial": firewall.serial,
                "firewall_name": firewall.hostname,
                "management_ip": management_ip,
            },
        )

        for subnet_index, subnet in enumerate(
            iter_site_subnet_candidates(firewall)
        ):
            address_space_id = subnet.record.address_space_id

            observation = PrefixObservation(
                local_ref=f"{local_ref}:prefix:{subnet_index}",
                prefix=subnet.prefix,
                observation_kind=subnet.source,
                routing_context=subnet.virtual_router,
                address_space_id=address_space_id,
                local_device_ref=local_ref,
            )

            prefixes.append(observation)

            counts[f"prefix_{subnet.source}"] += 1
            counts[f"selection_{subnet.decision}"] += 1

            if address_space_id is None:
                counts["prefix_unmapped"] += 1
            else:
                counts["prefix_mapped"] += 1

            logger.debug(
                "Panorama prefix normalized",
                extra={
                    "source_file": str(path),
                    "firewall_serial": firewall.serial,
                    "prefix": str(subnet.prefix),
                    "prefix_source": subnet.source,
                    "virtual_router": subnet.virtual_router,
                    "address_space_id": (
                        str(address_space_id)
                        if address_space_id is not None
                        else None
                    ),
                    "selection": subnet.decision,
                },
            )

    dataset = SourceDataset(
        source=source,
        devices=tuple(devices),
        network_prefixes=tuple(prefixes),
        collected_at=result.collected_at_utc,
    )

    logger.info(
        "Panorama export normalized",
        extra={
            "source_file": str(path),
            "panorama": result.panorama,
            "source_id": str(dataset.source.source_id),
            "dataset_id": str(dataset.dataset_id),
            "collected_at": dataset.collected_at.isoformat(),
            "firewall_count": counts["firewalls"],
            "device_observation_count": len(dataset.devices),
            "prefix_observation_count": len(dataset.network_prefixes),
            "connected_prefix_count": counts["prefix_connected"],
            "static_prefix_count": counts["prefix_static"],
            "prefix_mapped": counts["prefix_mapped"],
            "prefix_unmapped": counts["prefix_unmapped"],
            "parser_issue_count": counts["parser_issues"],
            "collection_failure_count": counts["collection_failures"],
        },
    )

    for issue in result.issues:
        log = {
            "error": logger.error,
            "warning": logger.warning,
            "info": logger.info,
        }.get(issue.severity, logger.warning)

        log(
            "Panorama parsing issue",
            extra={
                "source_file": str(path),
                "firewall_serial": issue.firewall_serial,
                "json_path": issue.path,
                "reason": issue.reason,
            },
        )

    for failure in result.collection_failures:
        logger.warning(
            "Panorama collection failure",
            extra={
                "source_file": str(path),
                "firewall_serial": failure.serial,
                "firewall_name": failure.hostname,
                "section": failure.section,
                "error": failure.error,
            },
        )

    return dataset, counts


def configure_logging(debug: bool) -> None:
    level = "DEBUG" if debug else "INFO"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = Path("logs") / f"panorama_import_{timestamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    setup_logging(
        LoggingSettings(
            targets_json=json.dumps(
                [
                    {
                        "name": "console",
                        "output": "stdout",
                        "level": level,
                        "format": "text",
                    },
                    {
                        "name": "file",
                        "output": "file",
                        "level": level,
                        "format": "text",
                        "file_path": str(log_path),
                    },
                ]
            )
        )
    )


def main() -> int:
    """Normalize Panorama exports without writing to SQLite."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("exports", nargs="+", type=Path)
    parser.add_argument(
        "--address-space-config",
        type=Path,
        default=None,
    )
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    configure_logging(args.debug)

    try:
        mapping = load_address_space_mapping(
            args.address_space_config
        )
    except Exception:
        logger.exception("Failed to load AddressSpace configuration")
        return 1

    failures = 0

    for path in args.exports:
        try:
            import_panorama(
                path,
                address_space_mapping=mapping,
            )
        except Exception:
            failures += 1
            logger.exception(
                "Panorama import failed",
                extra={"source_file": str(path)},
            )

    logger.info(
        "Panorama import finished",
        extra={
            "total_files": len(args.exports),
            "failed_files": failures,
        },
    )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
