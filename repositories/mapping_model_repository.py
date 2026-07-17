"""Repository for mapping_models table (alias -> multiple supplier models)."""
import logging
from typing import List
from provider.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class MappingModelRepository:
    """Repository for mapping_models table (alias -> multiple supplier models)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_by_alias(self, alias_name: str) -> List[dict]:
        """Get all supplier models bound to a mapping alias."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM mapping_models WHERE alias_name = ? ORDER BY id",
                (alias_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_model(self, alias_name: str, supplier_id: int, model_name: str) -> dict:
        """Add a supplier model to a mapping alias. Raises on UNIQUE conflict."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO mapping_models (alias_name, supplier_id, model_name)
                   VALUES (?, ?, ?)""",
                (alias_name, supplier_id, model_name),
            )
            cursor = conn.execute(
                "SELECT * FROM mapping_models WHERE alias_name = ? AND id = last_insert_rowid()",
                (alias_name,),
            )
            row = cursor.fetchone()
            result = dict(row)
            logger.info(
                f"Added mapping model: alias={alias_name}, supplier_id={supplier_id}, model={model_name}"
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
