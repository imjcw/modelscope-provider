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

    def bulk_upsert(self, mappings):
        """Bulk upsert model mappings.

        Accepts either a dict like {'hy3': 'hy3-actual'} (legacy format)
        or a list of full mapping record dicts (as produced by export_config).
        When a list is given, each dict should contain at least ``alias_name``
        and ``actual_model_id``; ``description`` and ``status`` are optional.
        """
        with self.db.get_connection() as conn:
            if isinstance(mappings, dict):
                # Legacy format: {alias_name: actual_model_id}
                for alias_name, actual_model_id in mappings.items():
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
            else:
                # New format: list of full mapping records
                for m in mappings:
                    alias_name = m.get("alias_name")
                    if not alias_name:
                        continue
                    actual_model_id = m.get("actual_model_id") or alias_name
                    description = m.get("description", "")
                    status = m.get("status", "active")
                    conn.execute(
                        """INSERT INTO model_mappings
                               (alias_name, actual_model_id, description, status)
                           VALUES (?, ?, ?, ?)
                           ON CONFLICT(alias_name)
                           DO UPDATE SET actual_model_id = excluded.actual_model_id,
                                         description = excluded.description,
                                         status = excluded.status,
                                         updated_at = CURRENT_TIMESTAMP""",
                        (alias_name, actual_model_id, description, status),
                    )
                logger.info(f"Bulk upserted {len(mappings)} model mappings (full records)")

    def rename(self, old_alias: str, new_alias: str) -> Optional[dict]:
        """Rename a mapping alias, cascading to mapping_models and model_alias_cache.

        The alias is the FK target of ``mapping_models.alias_name``, so the new
        row is inserted first, then dependent rows are re-pointed, then the old
        row is deleted.
        """
        new_alias = (new_alias or "").strip()
        old_alias = (old_alias or "").strip()
        if not new_alias or new_alias == old_alias:
            return self.find_by_alias(old_alias)[0] if self.find_by_alias(old_alias) else None

        with self.db.get_connection() as conn:
            old = conn.execute(
                "SELECT * FROM model_mappings WHERE alias_name = ?", (old_alias,)
            ).fetchone()
            if not old:
                return None
            conflict = conn.execute(
                "SELECT 1 FROM model_mappings WHERE alias_name = ?", (new_alias,)
            ).fetchone()
            if conflict:
                raise ValueError(f"智能路由ID {new_alias} 已存在")
            # 1. Insert new mapping row (copies fields from the old row)
            conn.execute(
                """INSERT INTO model_mappings (alias_name, actual_model_id, description, status)
                   VALUES (?, ?, ?, ?)""",
                (new_alias, old["actual_model_id"], old["description"], old["status"]),
            )
            # 2. Re-point dependent rows to the new alias
            conn.execute(
                "UPDATE mapping_models SET alias_name = ? WHERE alias_name = ?",
                (new_alias, old_alias),
            )
            conn.execute(
                "UPDATE model_alias_cache SET alias_name = ? WHERE alias_name = ?",
                (new_alias, old_alias),
            )
            # 3. Drop the old mapping row (remaining dependent rows cascade)
            conn.execute("DELETE FROM model_mappings WHERE alias_name = ?", (old_alias,))
        return self.find_by_alias(new_alias)[0] if self.find_by_alias(new_alias) else None

    def delete_by_alias(self, alias_name: str) -> int:
        """Delete all mappings for an alias."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM model_mappings WHERE alias_name = ?", (alias_name,))
            return cursor.rowcount
