"""Repository for mapping_models table (alias -> multiple supplier models).

mapping_models now stores ``supplier_model_id`` (FK -> supplier_models.id).
All read queries JOIN supplier_models to resolve the model name, type and
context length — so bindings automatically follow renames and deletions.
"""

import logging
from typing import List

from core.database import DatabaseManager

logger = logging.getLogger(__name__)

# _base_select is shared by find_by_alias, add_model (confirmation) and
# get_by_supplier so every read path returns a consistent dict:
#   id, alias_name, supplier_model_id, supplier_id, model_name, sort_order,
#   created_at, updated_at, model_type, context_length
_base_select = """
    mm.id, mm.alias_name, mm.supplier_model_id, sm.supplier_id,
    sm.model_name, mm.sort_order, mm.created_at, mm.updated_at,
    sm.model_type, sm.context_length
"""


class MappingModelRepository:
    """Repository for mapping_models table (alias -> multiple supplier models)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_by_alias(self, alias_name: str) -> List[dict]:
        """Get all supplier models bound to a mapping alias.

        JOINs with supplier_models on ``supplier_model_id`` to resolve
        ``model_name``, ``model_type`` and ``context_length``.
        If the supplier model was deleted the FK CASCADE removes the binding,
        so every row returned is guaranteed valid.

        Ordered by sort_order, then id.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                f"""SELECT {_base_select}
                   FROM mapping_models mm
                   INNER JOIN supplier_models sm ON sm.id = mm.supplier_model_id
                   WHERE mm.alias_name = ?
                   ORDER BY mm.sort_order ASC, mm.id ASC""",
                (alias_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_model(
        self, alias_name: str, supplier_model_id: int, sort_order: int = 0
    ) -> dict:
        """Add a supplier model to a mapping alias. Raises on UNIQUE conflict.

        Args:
            supplier_model_id: FK to the ``supplier_models`` row.
            sort_order: position in the binding list (0-based).
        """
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO mapping_models
                       (alias_name, supplier_model_id, sort_order)
                   VALUES (?, ?, ?)""",
                (alias_name, supplier_model_id, sort_order),
            )
            cursor = conn.execute(
                f"""SELECT {_base_select}
                   FROM mapping_models mm
                   INNER JOIN supplier_models sm ON sm.id = mm.supplier_model_id
                   WHERE mm.alias_name = ? AND mm.id = last_insert_rowid()""",
                (alias_name,),
            )
            row = cursor.fetchone()
            result = dict(row)
            logger.info(
                f"Added mapping model: alias={alias_name}, "
                f"supplier_model_id={supplier_model_id}, sort_order={sort_order}"
            )
            return result

    def remove_model(self, model_id: int) -> bool:
        """Remove a mapping model by its row id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM mapping_models WHERE id = ?", (model_id,)
            )
            return cursor.rowcount > 0

    def get_by_supplier(self, supplier_id: int) -> List[dict]:
        """Get all mapping models for a specific supplier.

        Finds bindings whose bound supplier_model belongs to ``supplier_id``.
        Returns dicts with model_name resolved via JOIN.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                f"""SELECT {_base_select}
                   FROM mapping_models mm
                   INNER JOIN supplier_models sm ON sm.id = mm.supplier_model_id
                   WHERE sm.supplier_id = ?
                   ORDER BY mm.alias_name""",
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
                    "UPDATE mapping_models SET sort_order = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ? AND alias_name = ?",
                    (idx, mid, alias_name),
                )
        return self.find_by_alias(alias_name)
