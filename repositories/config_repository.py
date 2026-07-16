import logging
from typing import Optional

from provider.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ConfigRepository:
    """Repository for system_config table (key-value store)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get(self, key: str) -> Optional[str]:
        """Get config value by key."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all(self) -> dict:
        """Get all config as a dict."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT key, value, description FROM system_config ORDER BY key")
            return {row["key"]: {"value": row["value"], "description": row["description"]}
                    for row in cursor.fetchall()}

    def set(self, key: str, value: str):
        """Set or update a config value."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO system_config (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
                (key, value),
            )

    def bulk_set(self, config: dict):
        """Bulk set config values."""
        for key, value in config.items():
            self.set(key, str(value))
        logger.info(f"Bulk updated {len(config)} config values")
