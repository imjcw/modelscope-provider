"""Migrator — executes pending migrations in version order."""

import logging
import sqlite3

from core.database import DatabaseManager
from core.migrations.registry import get_all_migrations

logger = logging.getLogger(__name__)

_VERSION_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS schema_versions (
        version INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


class Migrator:
    """Run, inspect, and rollback schema migrations."""

    def __init__(self, database: DatabaseManager, migrations: list | None = None):
        self.db = database
        self._migrations = migrations  # None → use global registry

    def _ensure_version_table(self) -> None:
        with self.db.get_connection() as conn:
            conn.execute(_VERSION_TABLE_SQL)

    def _get_applied_versions(self) -> set[int]:
        self._ensure_version_table()
        with self.db.get_connection() as conn:
            return {row["version"] for row in conn.execute("SELECT version FROM schema_versions")}

    def _get_migrations(self) -> list:
        return self._migrations if self._migrations is not None else get_all_migrations()

    def run(self) -> None:
        """Execute all pending migrations in version order."""
        applied = self._get_applied_versions()
        migrations = self._get_migrations()
        pending = [m for m in migrations if m.version not in applied]

        if not pending:
            logger.info("No pending migrations")
            return

        for m in pending:
            logger.info(f"Running migration {m.version}: {m.description}")
            with self.db.get_connection() as conn:
                m.up(conn)
                conn.execute(
                    "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
                    (m.version, m.description),
                )
            logger.info(f"Migration {m.version} applied")

    def status(self) -> list[dict]:
        """List all migrations with their applied status."""
        applied = self._get_applied_versions()
        migrations = self._get_migrations()
        return [
            {
                "version": m.version,
                "description": m.description,
                "applied": m.version in applied,
            }
            for m in migrations
        ]

    def rollback(self, target: int) -> None:
        """Rollback to target version, calling down() in reverse order."""
        applied = self._get_applied_versions()
        migrations = self._get_migrations()
        to_revert = [m for m in migrations if m.version > target and m.version in applied]

        if not to_revert:
            logger.info(f"Already at or below version {target}")
            return

        for m in reversed(to_revert):
            logger.info(f"Rolling back migration {m.version}: {m.description}")
            with self.db.get_connection() as conn:
                m.down(conn)
                conn.execute("DELETE FROM schema_versions WHERE version = ?", (m.version,))
            logger.info(f"Migration {m.version} rolled back")
