import logging
from typing import List, Optional

from provider.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class MappingRepository:
    """Repository for model_mappings table (alias → actual model id)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_all(self) -> List[dict]:
        """Get all mappings."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM model_mappings ORDER BY alias_name")
            return [dict(row) for row in cursor.fetchall()]

    def find_by_alias(self, alias_name: str) -> List[dict]:
        """Get mapping for a specific alias."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM model_mappings WHERE alias_name = ?", (alias_name,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def create(self, alias_name: str, actual_model_id: str) -> dict:
        """Create or replace a mapping entry."""
        with self.db.get_connection() as conn:
            # Upsert: insert or replace on UNIQUE(alias_name)
            conn.execute(
                """INSERT INTO model_mappings (alias_name, actual_model_id)
                   VALUES (?, ?)
                   ON CONFLICT(alias_name)
                   DO UPDATE SET actual_model_id = excluded.actual_model_id""",
                (alias_name, actual_model_id),
            )
            return self.find_by_alias(alias_name)

    def bulk_upsert(self, mappings: dict):
        """Bulk upsert mappings from a dict like {'hy3': 'hy3-actual'}.

        Keys are alias_name, values are actual_model_id.
        """
        with self.db.get_connection() as conn:
            for alias_name, actual_model_id in mappings.items():
                conn.execute(
                    """INSERT INTO model_mappings (alias_name, actual_model_id)
                       VALUES (?, ?)
                       ON CONFLICT(alias_name)
                       DO UPDATE SET actual_model_id = excluded.actual_model_id""",
                    (alias_name, actual_model_id),
                )
            logger.info(f"Bulk upserted {len(mappings)} model mappings")

    def delete_by_alias(self, alias_name: str) -> int:
        """Delete all mappings for an alias."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM model_mappings WHERE alias_name = ?", (alias_name,))
            return cursor.rowcount
