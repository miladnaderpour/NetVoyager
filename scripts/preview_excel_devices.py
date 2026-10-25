
"""Preview Excel device identity matching against NetVoyager SQLite.

Read a selected subset of Excel inventory and compare its observations
with existing canonical devices and discovery candidates.

This diagnostic never creates, modifies, promotes, or deletes inventory.
It does not treat management IP or hostname equality as proof of identity.
"""

from __future__ import annotations

import argparse
from collections import Counter
from ipaddress import IPv4Address
from pathlib import Path

from netvoyager_core.logging import get_logger
from netvoyager_database.engine import create_database_engine
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_import.inventory.excel import read_network_devices


logger = get_logger("scripts.preview_excel_devices")


def preview(
    excel_path: Path,
    database_path: Path,
    *,
    sheet_name: str | None = None,
    sites: set[str] | None = None,
    devices: set[str] | None = None,
) -> Counter[str]:
    """Preview selected Excel observations against an existing database."""
    if not excel_path.is_file():
        raise FileNotFoundError(f"Excel workbook not found: {excel_path}")

    if not database_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {database_path}")

    dataset = read_network_devices(
        excel_path,
        sheet_name=sheet_name,
        sites=sites,
        devices=devices,
    )

    engine = create_database_engine(
        f"sqlite:///{database_path.resolve().as_posix()}"
    )

    counts: Counter[str] = Counter()

    print(f"Source: {dataset.source.name}")
    print(f"Selected observations: {len(dataset.devices)}")
    print()

    try:
        session_factory = create_session_factory(engine)

        with NetworkInventoryUnitOfWork(session_factory) as uow:
            for observation in dataset.devices:
                name = (
                    observation.inventory_name
                    or observation.hostname
                )
                serial = (
                    observation.serial_number.strip()
                    if observation.serial_number
                    else None
                )

                canonical_matches = (
                    uow.devices.find_by_serial(serial)
                    if serial
                    else ()
                )

                candidate_matches = (
                    uow.discovery.find_by_serial(serial)
                    if serial
                    else ()
                )

                if not serial:
                    status = "missing_serial"
                    counts[status] += 1

                elif len(canonical_matches) > 1:
                    status = "ambiguous_canonical"
                    counts[status] += 1

                elif len(canonical_matches) == 1:
                    status = "canonical_serial_match"
                    counts[status] += 1

                elif len(candidate_matches) > 1:
                    status = "ambiguous_candidates"
                    counts[status] += 1

                elif len(candidate_matches) == 1:
                    status = "candidate_serial_match"
                    counts[status] += 1

                else:
                    by_name = (
                        uow.devices.find_by_name(name)
                        if name
                        else None
                    )

                    if by_name is not None:
                        status = "name_requires_review"
                    else:
                        status = "new_candidate"

                    counts[status] += 1

                print(
                    f"{status:25} "
                    f"site={str(observation.site or '-'):18} "
                    f"name={str(name or '-'):30} "
                    f"serial={str(serial or '-')}"
                )

                # Duplicate management IPs are reported separately.
                # An IP match never overrides physical identity.
                if observation.management_ip:
                    ip_matches = uow.devices.find_by_management_ip(
                        IPv4Address(observation.management_ip)
                    )

                    if ip_matches:
                        if (
                            len(canonical_matches) != 1
                            or any(
                                item.device_id
                                != canonical_matches[0].device_id
                                for item in ip_matches
                            )
                        ):
                            counts["management_ip_review"] += 1

                            print(
                                "  WARNING: management IP matches "
                                "another canonical record or lacks "
                                "a confirmed serial match"
                            )

            print()
            print("Summary")
            print("-" * 50)

            for key, count in sorted(counts.items()):
                print(f"{key:30} {count}")

            print(f"{'total_observations':30} {len(dataset.devices)}")

    finally:
        engine.dispose()

    return counts


def main() -> int:
    """Run the read-only device matching diagnostic."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("excel", type=Path)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--sheet", type=str, default=None)

    parser.add_argument(
        "--site",
        action="append",
        default=None,
        help="Select site; may be repeated",
    )

    parser.add_argument(
        "--device",
        action="append",
        default=None,
        help="Select device name, hostname or serial; may be repeated",
    )

    args = parser.parse_args()

    try:
        preview(
            args.excel,
            args.database,
            sheet_name=args.sheet,
            sites=set(args.site) if args.site is not None else None,
            devices=(
                set(args.device)
                if args.device is not None
                else None
            ),
        )
    except (OSError, ValueError) as exc:
        logger.error(
            "Excel device reconciliation preview failed: %s",
            exc,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
