import logging
from typing import List, Optional

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class MappingRepository:
    """Repository for model_mappings table (alias → actual model id)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_all(self) -> List[dict]:
        """Get all mappings, ordered by created_at desc."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM model_mappings ORDER BY created_at DESC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def find_by_alias(self, alias_name: str) -> List[dict]:
        """Get mapping for a specific alias."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM model_mappings WHERE alias_name = ?", (alias_name,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def create(self, alias_name: str, actual_model_id: str,
               description: str = "", status: str = "active") -> dict:
        """Create or replace a mapping entry.

        Args:
            alias_name: virtual model ID (unique).
            actual_model_id: fallback real model id.
            description: optional description text.
            status: 'active' or 'disabled'.
        """
        with self.db.get_connection() as conn:
            # Upsert: insert or replace on UNIQUE(alias_name)
            conn.execute(
                """INSERT INTO model_mappings (alias_name, actual_model_id, description, status)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(alias_name)
                   DO UPDATE SET actual_model_id = excluded.actual_model_id,
                                 description = excluded.description,
                                 status = excluded.status,
                                 updated_at = CURRENT_TIMESTAMP""",
                (alias_name, actual_model_id, description, status),
            )
        return self.find_by_alias(alias_name)

    def update(self, alias_name: str, **kwargs) -> Optional[dict]:
        """Update specific fields of a mapping alias.

        Supported kwargs: actual_model_id, description, status.
        Returns updated mapping or None if not found.
        """
        allowed = {"actual_model_id", "description", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not fields:
            return self.find_by_alias(alias_name)[0] if self.find_by_alias(alias_name) else None

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(fields.values()) + [alias_name]

        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE model_mappings SET {set_clause} WHERE alias_name = ?",
                values,
            )
        return self.find_by_alias(alias_name)[0] if self.find_by_alias(alias_name) else None

    def update_status(self, alias_name: str, status: str) -> Optional[dict]:
        """Set status ('active' or 'disabled') for a mapping alias."""
        return self.update(alias_name, status=status)

    def toggle_status(self, alias_name: str) -> Optional[dict]:
        """Toggle status between 'active' and 'disabled'.

        Returns the updated mapping dict, or None if not found.
        """
        rows = self.find_by_alias(alias_name)
        if not rows:
            return None
        new_status = "disabled" if rows[0].get("status", "active") == "active" else "active"
        return self.update(alias_name, status=new_status)

    def bulk_upsert(self, mappings: dict):
        """Bulk upsert mappings from a dict like {'hy3': 'hy3-actual'}.

        Keys are alias_name, values are actual_model_id.

        Empty values fall back to the alias_name itself (virtual model ID
        is used as the actual model ID when no explicit mapping is given).
        """
        with self.db.get_connection() as conn:
            for alias_name, actual_model_id in mappings.items():
                # Fallback: empty value means use alias as actual model id
                effective_id = actual_model_id if actual_model_id else alias_name
                conn.execute(
                    """INSERT INTO model_mappings (alias_name, actual_model_id)
                       VALUES (?, ?)
                       ON CONFLICT(alias_name)
                       DO UPDATE SET actual_model_id = excluded.actual_model_id,
                                     updated_at = CURRENT_TIMESTAMP""",
                    (alias_name, effective_id),
                )
        logger.info(f"Bulk upserted {len(mappings)} model mappings")

    def delete_by_alias(self, alias_name: str) -> int:
        """Delete all mappings for an alias."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM model_mappings WHERE alias_name = ?", (alias_name,))
            return cursor.rowcount
