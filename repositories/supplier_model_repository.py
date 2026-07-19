import logging
from typing import List, Optional

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class SupplierModelRepository:
    """Repository for supplier_models table."""

    def __init__(self, db: DatabaseManager):
        self.db = db

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
        """Replace all models for a supplier with the given list.

        Each item in models is a dict with keys: model_name, model_type, context_length (optional).
        """
        with self.db.get_connection() as conn:
            # Delete existing models for this supplier first
            conn.execute(
                "DELETE FROM supplier_models WHERE supplier_id = ?", (supplier_id,)
            )
            # Insert new models
            for m in models:
                conn.execute(
                    """INSERT INTO supplier_models (supplier_id, model_name, model_type, context_length)
                       VALUES (?, ?, ?, ?)""",
                    (supplier_id, m["model_name"], m["model_type"], m.get("context_length")),
                )
            logger.info(f"Bulk upserted {len(models)} models for supplier {supplier_id}")

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
