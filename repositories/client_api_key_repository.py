"""Repository for client_api_keys table - downstream client API key management."""
import logging
import uuid
from typing import List, Optional

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ClientApiKeyRepository:
    """Repository for client API keys table CRUD."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_all(self) -> List[dict]:
        """Get all client API keys."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM client_api_keys ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]

    def find_by_id(self, key_id: int) -> Optional[dict]:
        """Get client API key by internal id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM client_api_keys WHERE id = ?", (key_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_name(self, name: str) -> Optional[dict]:
        """Get client API key by unique name."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM client_api_keys WHERE name = ?", (name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_key_value(self, key_value: str) -> Optional[dict]:
        """Get client API key by key value (for authentication)."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM client_api_keys WHERE key_value = ?", (key_value,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def create(self, name: str, description: str = "") -> dict:
        """Create a new client API key. key_value is auto-generated as nk-{uuid}."""
        key_value = f"nk-{uuid.uuid4().hex[:32]}"
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO client_api_keys (key_value, name, description, status)
                   VALUES (?, ?, ?, 'active')""",
                (key_value, name, description),
            )
            conn.commit()
            result = self.find_by_id(cursor.lastrowid)
            logger.info(
                f"Created client API key '{name}' (id={cursor.lastrowid}, key={key_value[:8]}...)"
            )
            return result

    def update(
        self, key_id: int, name: str = None, description: str = None,
        status: str = None
    ) -> Optional[dict]:
        """Update client API key fields."""
        fields = {}
        if name is not None:
            fields["name"] = name
        if description is not None:
            fields["description"] = description
        if status is not None:
            fields["status"] = status

        if not fields:
            return None

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        values.append(key_id)

        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE client_api_keys SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
        return self.find_by_id(key_id)

    def delete(self, key_id: int) -> bool:
        """Delete a client API key."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM client_api_keys WHERE id = ?", (key_id,)
            )
            return cursor.rowcount > 0

    def count(self) -> int:
        """Count total client API keys."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM client_api_keys")
            return cursor.fetchone()[0]
