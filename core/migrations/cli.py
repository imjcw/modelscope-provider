"""CLI entry point: python -m core.migrations.cli [run|status|rollback N]."""

import argparse
import logging
import sys

from core.config import ConfigManager
from core.database import DatabaseManager
from core.migrations.migrator import Migrator

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DB schema migration tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run all pending migrations")
    subparsers.add_parser("status", help="Show migration status")

    rollback_parser = subparsers.add_parser("rollback", help="Rollback to target version")
    rollback_parser.add_argument("target", type=int, help="Target version number")

    args = parser.parse_args(argv)

    config = ConfigManager()
    database = DatabaseManager(config.get_database_url())
    migrator = Migrator(database)

    if args.command == "run":
        migrator.run()
        return 0
    if args.command == "status":
        for entry in migrator.status():
            flag = "✓" if entry["applied"] else "✗"
            print(f"  {flag} {entry['version']:>3}: {entry['description']}")
        return 0
    if args.command == "rollback":
        migrator.rollback(args.target)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
