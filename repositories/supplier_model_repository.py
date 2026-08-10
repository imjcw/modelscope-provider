import logging
from typing import List, Optional

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class SupplierModelRepository:
    """Repository for supplier_models table."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_by_id(self, model_id: int) -> Optional[dict]:
        """Get a single supplier model by its row id, or None."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM supplier_models WHERE id = ?",
                (model_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_supplier(self, supplier_id: int) -> List[dict]:
        """Get all models supported by a supplier."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM supplier_models WHERE supplier_id = ? ORDER BY model_name",
                (supplier_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def create(
        self,
        supplier_id: int,
        model_name: str,
        model_type: str,
        context_length: Optional[int] = None,
    ) -> dict:
        """Create a supplier-model association. Raises on UNIQUE conflict."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO supplier_models (supplier_id, model_name, model_type, context_length)
                   VALUES (?, ?, ?, ?)""",
                (supplier_id, model_name, model_type, context_length),
            )
            cursor = conn.execute(
                "SELECT * FROM supplier_models WHERE supplier_id = ? AND model_name = ?",
                (supplier_id, model_name),
            )
            row = cursor.fetchone()
            result = dict(row)
            logger.info(
                f"Created supplier model: supplier_id={supplier_id}, model={model_name}, "
                f"type={model_type}, context_length={context_length}"
            )
            return result

    def delete(self, model_id: int) -> bool:
        """Delete a supplier-model association by its row id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM supplier_models WHERE id = ?", (model_id,))
            return cursor.rowcount > 0

    def delete_by_supplier(self, supplier_id: int) -> int:
        """Delete all models for a supplier. Returns deleted row count."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM supplier_models WHERE supplier_id = ?", (supplier_id,)
            )
            return cursor.rowcount

    def bulk_upsert(
        self, supplier_id: int, models: List[dict]
    ) -> None:
        """Upsert the model catalog for a supplier without breaking bindings.

        Each item in models is a dict with keys: model_name, model_type,
        context_length (optional).

        Uses ``INSERT ... ON CONFLICT DO UPDATE`` so that rows already
        referenced by ``mapping_models.supplier_model_id`` are **updated in
        place** rather than deleted-and-reinserted.  This avoids the FK
        ``ON DELETE CASCADE`` that would otherwise silently remove routing
        bindings when a supplier is edited.
        """
        with self.db.get_connection() as conn:
            for m in models:
                conn.execute(
                    """INSERT INTO supplier_models
                           (supplier_id, model_name, model_type, context_length)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(supplier_id, model_name)
                       DO UPDATE SET
                           model_type = excluded.model_type,
                           context_length = excluded.context_length""",
                    (supplier_id, m["model_name"], m["model_type"], m.get("context_length")),
                )
            logger.info(
                "Bulk upserted %d models for supplier %d",
                len(models), supplier_id,
            )

    def find_suppliers_for_model(self, model_name: str) -> List[dict]:
        """Find active suppliers that support a given model name.

        Returns full account dicts from the accounts table, joined with
        the matching supplier_models row.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """SELECT a.*, sm.model_type, sm.context_length
                   FROM accounts a
                   INNER JOIN supplier_models sm ON sm.supplier_id = a.id
                   WHERE sm.model_name = ? AND a.status = 'active'
                   ORDER BY a.id""",
                (model_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def find_by_supplier_batch(self, supplier_ids: List[int]) -> dict:
        """Batch version of :meth:`find_by_supplier`.

        Returns ``{supplier_id: [model_dicts]}``. Used by ``get_suppliers`` and
        the export paths to load every supplier's model catalog in one query
        instead of one per supplier (P2 / P6).
        """
        if not supplier_ids:
            return {}
        ids = list(supplier_ids)
        result = {sid: [] for sid in ids}
        placeholders = ",".join("?" * len(ids))
        with self.db.get_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM supplier_models "
                f"WHERE supplier_id IN ({placeholders}) "
                f"ORDER BY supplier_id, model_name",
                ids,
            ).fetchall()
            for row in rows:
                result.setdefault(row["supplier_id"], []).append(dict(row))
        return result
