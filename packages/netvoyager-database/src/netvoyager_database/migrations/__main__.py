
"""Execute package-owned NetVoyager database migrations.

Examples:
    python -m netvoyager_database.migrations upgrade --url sqlite:///netvoyager.db
    python -m netvoyager_database.migrations current --url sqlite:///netvoyager.db
    python -m netvoyager_database.migrations revision --url sqlite:///empty.db
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from netvoyager_core.logging import get_logger


logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent


def create_migration_config(database_url: str) -> Config:
    """Configure Alembic using migrations bundled with the package."""
    config = Config()

    config.set_main_option(
        "script_location",
        str(MIGRATIONS_DIR),
    )

    config.set_main_option(
        "path_separator",
        "os",
    )

    config.attributes["database_url"] = database_url

    return config


def main() -> None:
    """Execute an explicit database migration operation."""
    parser = argparse.ArgumentParser(
        description="NetVoyager database migrations",
    )

    parser.add_argument(
        "action",
        choices=[
            "upgrade",
            "downgrade",
            "current",
            "heads",
            "revision",
            "check",
        ],
    )

    parser.add_argument(
        "--url",
        default=os.environ.get("NETVOYAGER_DATABASE_URL"),
        help="SQLAlchemy database URL",
    )

    parser.add_argument(
        "--revision",
        default=None,
        help="Target revision or downgrade target",
    )

    parser.add_argument(
        "--message",
        default=None,
        help="Message for a newly generated revision",
    )

    args = parser.parse_args()

    if args.action != "heads" and not args.url:
        parser.error(
            "Specify --url or NETVOYAGER_DATABASE_URL."
        )

    config = create_migration_config(args.url or "")

    logger.info(
        "NetVoyager database migration command started",
        extra={"action": args.action},
    )

    if args.action == "upgrade":
        command.upgrade(config, args.revision or "head")

    elif args.action == "downgrade":
        if not args.revision:
            parser.error("Downgrade requires --revision.")

        command.downgrade(config, args.revision)

    elif args.action == "current":
        command.current(config)

    elif args.action == "heads":
        command.heads(config)

    elif args.action == "revision":
        if not args.message:
            parser.error("Revision requires --message.")

        command.revision(
            config,
            message=args.message,
            autogenerate=True,
        )

    elif args.action == "check":
        command.check(config)

    logger.info(
        "NetVoyager database migration command completed",
        extra={"action": args.action},
    )


if __name__ == "__main__":
    main()
