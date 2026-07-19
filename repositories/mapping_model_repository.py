"""Repository for mapping_models table (alias -> multiple supplier models)."""
import logging
from typing import List
from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class MappingModelRepository:
    """Repository for mapping_models table (alias -> multiple supplier models)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_by_alias(self, alias_name: str) -> List[dict]:
        """Get all supplier models bound to a mapping alias.

        Joins with supplier_models to fetch model_type and context_length.
        Ordered by sort_order, then id.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """SELECT mm.id, mm.alias_name, mm.supplier_id, mm.model_name,
                          mm.sort_order, mm.created_at, mm.updated_at,
                          sm.model_type, sm.context_length
                   FROM mapping_models mm
                   LEFT JOIN supplier_models sm
                       ON sm.supplier_id = mm.supplier_id AND sm.model_name = mm.model_name
                   WHERE mm.alias_name = ?
                   ORDER BY mm.sort_order ASC, mm.id ASC""",
                (alias_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_model(self, alias_name: str, supplier_id: int, model_name: str,
                  sort_order: int = 0) -> dict:
        """Add a supplier model to a mapping alias. Raises on UNIQUE conflict.

        Args:
            sort_order: position in the binding list (0-based).
        """
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO mapping_models (alias_name, supplier_id, model_name, sort_order)
                   VALUES (?, ?, ?, ?)""",
                (alias_name, supplier_id, model_name, sort_order),
            )
            cursor = conn.execute(
                """SELECT mm.id, mm.alias_name, mm.supplier_id, mm.model_name,
                          mm.sort_order, mm.created_at, mm.updated_at,
                          sm.model_type, sm.context_length
                   FROM mapping_models mm
                   LEFT JOIN supplier_models sm
                       ON sm.supplier_id = mm.supplier_id AND sm.model_name = mm.model_name
                   WHERE mm.alias_name = ? AND mm.id = last_insert_rowid()""",
                (alias_name,),
            )
            row = cursor.fetchone()
            result = dict(row)
            logger.info(
                f"Added mapping model: alias={alias_name}, supplier_id={supplier_id}, "
                f"model={model_name}, sort_order={sort_order}"
            )
            return result

    def remove_model(self, model_id: int) -> bool:
        """Remove a mapping model by its row id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM mapping_models WHERE id = ?", (model_id,))
            return cursor.rowcount > 0

    def get_by_supplier(self, supplier_id: int) -> List[dict]:
        """Get all mapping models for a specific supplier."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM mapping_models WHERE supplier_id = ? ORDER BY alias_name",
                (supplier_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def reorder(self, alias_name: str, ordered_ids: List[int]) -> List[dict]:
        """Update sort_order for all bindings of an alias based on the given id list.

        Args:
            alias_name: the virtual model ID.
            ordered_ids: list of mapping_models ids in the desired order.

        Returns:
            Updated list of bindings (ordered).
        """
        with self.db.get_connection() as conn:
            for idx, mid in enumerate(ordered_ids):
                conn.execute(
                    "UPDATE mapping_models SET sort_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND alias_name = ?",
                    (idx, mid, alias_name),
                )
        return self.find_by_alias(alias_name)
