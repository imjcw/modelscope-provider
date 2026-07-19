import logging
import uuid
from typing import List, Optional

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class AccountRepository:
    """Repository for accounts table CRUD."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_all(self) -> List[dict]:
        """Get all accounts."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM accounts ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]

    def find_by_id(self, account_id: int) -> Optional[dict]:
        """Get account by id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_account_id(self, account_id: str) -> Optional[dict]:
        """Get account by account_id field."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_name(self, name: str) -> Optional[dict]:
        """Get account by name (name is UNIQUE)."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM accounts WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_active(self) -> List[dict]:
        """Get only active accounts."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM accounts WHERE status = 'active' ORDER BY id"
            )
            return [dict(row) for row in cursor.fetchall()]

    def create(self, name: str, api_key: str, base_url: str,
               status: str = "active") -> dict:
        """Create a new account. account_id is auto-generated as UUID."""
        account_id = uuid.uuid4().hex
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO accounts (account_id, name, api_key, base_url, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, name, api_key, base_url, status),
            )
            conn.commit()
            result = self.find_by_id(cursor.lastrowid)
            logger.info(f"Created account {account_id} (name={name}, id={cursor.lastrowid})")
            return result

    def update(self, account_id: int, **kwargs) -> Optional[dict]:
        """Update account fields."""
        allowed = {"api_key", "base_url", "status", "account_id", "name"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return None

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        values.append(account_id)

        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE accounts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
        # Read back after commit so the change is visible across connections.
        return self.find_by_id(account_id)

    def delete(self, account_id: int) -> bool:
        """Delete an account."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            return cursor.rowcount > 0

    def count(self) -> int:
        """Count total accounts."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM accounts")
            return cursor.fetchone()[0]
