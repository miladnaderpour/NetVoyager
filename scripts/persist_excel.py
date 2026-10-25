
"""Import Excel device observations into an existing NetVoyager database.

This script is a CLI entry point only.

Responsibilities:
    - Parse CLI arguments.
    - Read and normalize the Excel inventory.
    - Load source policies.
    - Initialize database access.
    - Invoke the device discovery application service.
    - Commit the transaction or perform a dry run.
    - Display import statistics.

Device matching, candidate enrichment, canonical reconciliation,
and Finding generation belong to the discovery service and Analysis.

The database schema must already be migrated.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.devices.discovery_service import (
    import_device_dataset,
)
from netvoyager_core.logging import get_logger
from netvoyager_database.engine import create_database_engine
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_import.inventory.excel import read_network_devices


logger = get_logger("scripts.persist_excel")


def parse_args() -> argparse.Namespace:
    """Parse Excel inventory import arguments."""
    parser = argparse.ArgumentParser(
        description="Import Excel device observations into NetVoyager.",
    )

    parser.add_argument(
        "excel",
        type=Path,
        help="Path to the Excel inventory workbook.",
    )

    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Path to an existing SQLite database.",
    )

    parser.add_argument(
        "--policies",
        type=Path,
        default=Path("examples/policies"),
        help="Directory containing source policy definitions.",
    )

    parser.add_argument(
        "--sheet",
        default=None,
        help="Excel worksheet name.",
    )

    parser.add_argument(
        "--site",
        action="append",
        help="Import only a specified site (repeatable).",
    )

    parser.add_argument(
        "--device",
        action="append",
        help="Import only a specified device (repeatable).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate the import without committing changes.",
    )

    return parser.parse_args()


def print_summary(
    counts: Counter[str],
    *,
    dry_run: bool,
) -> None:
    """Display device discovery statistics."""
    print()
    print("Excel Device Discovery")
    print("=" * 48)

    for name, value in sorted(counts.items()):
        print(f"{name:39} {value}")

    print()
    print(
        "Mode:",
        "DRY RUN - no changes committed"
        if dry_run
        else "COMMITTED",
    )


def main() -> int:
    """Execute the Excel device discovery import."""
    args = parse_args()

    if not args.excel.is_file():
        raise SystemExit(
            f"Excel workbook not found: {args.excel}"
        )

    if not args.database.is_file():
        raise SystemExit(
            f"SQLite database not found: {args.database}"
        )

    # ---------------------------------------------------------
    # 1. Normalize source data
    # ---------------------------------------------------------

    dataset = read_network_devices(
        args.excel,
        sheet_name=args.sheet,
        sites=args.site,
        devices=args.device,
    )

    # ---------------------------------------------------------
    # 2. Load source policies
    # ---------------------------------------------------------

    policies = PolicyEngine()
    policies.load_directory(args.policies)

    if policies.get(
        dataset.source.name,
        dataset.source.source_type,
    ) is None:
        raise SystemExit(
            "Excel inventory source policy is not configured."
        )

    # ---------------------------------------------------------
    # 3. Initialize database access
    # ---------------------------------------------------------

    database_url = (
        f"sqlite:///{args.database.resolve().as_posix()}"
    )

    engine = create_database_engine(database_url)

    try:
        session_factory = create_session_factory(engine)

        # -----------------------------------------------------
        # 4. Execute discovery within one transaction
        # -----------------------------------------------------

        with NetworkInventoryUnitOfWork(session_factory) as uow:
            counts = import_device_dataset(
                dataset=dataset,
                policies=policies,
                uow=uow,
                dry_run=args.dry_run,
            )

            if not args.dry_run:
                uow.commit()

        # -----------------------------------------------------
        # 5. Display results
        # -----------------------------------------------------

        print_summary(
            counts,
            dry_run=args.dry_run,
        )

        logger.info(
            "Excel discovery import completed",
            extra={
                "source": dataset.source.name,
                "dry_run": args.dry_run,
                "observations": counts["observations"],
                "candidates_created": counts["candidates_created"],
                "candidates_reused": counts["candidates_reused"],
                "findings_created": counts["findings_created"],
            },
        )

        return 0

    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
