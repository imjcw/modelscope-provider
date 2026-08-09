import logging
import uuid
from typing import Dict, List, Optional

from core.database import DatabaseManager
from models.account import DEFAULT_PROVIDER_TYPE

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

    def find_by_ids(self, ids: List[int]) -> Dict[int, dict]:
        """Get accounts by multiple IDs, returns dict mapping id -> account."""
        if not ids:
            return {}
        
        with self.db.get_connection() as conn:
            # Use parameterized IN clause with safe expansion
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"SELECT * FROM accounts WHERE id IN ({placeholders})",
                ids
            )
            accounts = {}
            for row in cursor.fetchall():
                account = dict(row)
                accounts[account["id"]] = account
            return accounts

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

    def create(self, name: str, base_url: str,
               status: str = "active", provider_type: str = DEFAULT_PROVIDER_TYPE,
               api_keys: Optional[List[str]] = None) -> dict:
        """Create a new account. account_id is auto-generated as UUID.

        All API keys are stored in ``account_api_keys`` (the legacy single
        ``accounts.api_key`` column was dropped in migration 023). At least one
        key is required; the first key is flagged as the primary ("主密钥").
        """
        keys = [k.strip() for k in (api_keys or []) if k and k.strip()]
        if not keys:
            raise ValueError("At least one API key is required")
        account_id = uuid.uuid4().hex
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO accounts (account_id, name, base_url, provider_type, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, name, base_url, provider_type, status),
            )
            new_id = cursor.lastrowid
            for sort_order, key in enumerate(keys):
                conn.execute(
                    "INSERT INTO account_api_keys "
                    "(account_id, api_key, status, alias, sort_order) VALUES (?, ?, 'active', ?, ?)",
                    (new_id, key, "主密钥" if sort_order == 0 else "", sort_order),
                )
            conn.commit()
            result = self.find_by_id(new_id)
            logger.info(f"Created account {account_id} (name={name}, id={new_id})")
            return result

    def update(self, account_id: int, **kwargs) -> Optional[dict]:
        """Update account fields.

        API keys are managed via the dedicated account_api_keys endpoints
        (add/update/delete API key), not through this method.
        """
        # NOTE: "api_key" removed — the column no longer exists (migration 023).
        allowed = {"base_url", "status", "account_id", "name", "provider_type"}
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

    # ── Account API Keys (multi-key support) ──

    def find_api_keys(self, account_id: int) -> List[dict]:
        """Get all API keys for an account from account_api_keys."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM account_api_keys WHERE account_id = ? ORDER BY sort_order, id",
                (account_id,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def find_api_keys_by_account_ids(self, ids: List[int]) -> Dict[int, List[dict]]:
        """Batch variant of :meth:`find_api_keys` for multiple accounts.

        Returns ``{id(int): [key_record, ...]}`` from account_api_keys, using two
        queries instead of N to avoid per-candidate round-trips on the request
        hot path.
        """
        if not ids:
            return {}
        with self.db.get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            keys_by_acc: Dict[int, List[dict]] = {i: [] for i in ids}
            cursor = conn.execute(
                f"SELECT * FROM account_api_keys WHERE account_id IN ({placeholders}) "
                f"ORDER BY account_id, sort_order, id",
                ids,
            )
            for row in cursor.fetchall():
                keys_by_acc.setdefault(row["account_id"], []).append(dict(row))
        return keys_by_acc

    def replace_api_keys(self, account_id: int, keys: List[str]) -> None:
        """Replace all API keys for an account.

        Deletes existing keys and inserts the new list.
        Empty strings are ignored. All new keys are set to 'active'.
        """
        cleaned = [k.strip() for k in keys if k and k.strip()]
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM account_api_keys WHERE account_id = ?", (account_id,))
            for key in cleaned:
                conn.execute(
                    "INSERT INTO account_api_keys (account_id, api_key, status) VALUES (?, ?, 'active')",
                    (account_id, key),
                )
            conn.commit()

    def replace_api_keys_with_records(self, account_id: int, records: list) -> None:
        """Upsert API keys for an account using full records with status.

        Each record is a dict with at least 'api_key' and optionally
        'status' ('active' or 'frozen'), 'alias' (display name).
        Empty strings are ignored.

        Unlike the old delete-all-and-reinsert approach, this uses
        INSERT ... ON CONFLICT DO UPDATE so that keys not present in
        the records are preserved (not accidentally deleted).
        """
        cleaned = []
        for r in records:
            key = r.get("api_key", "").strip()
            if not key:
                continue
            cleaned.append(r)
        with self.db.get_connection() as conn:
            for sort_order, r in enumerate(cleaned):
                key = r.get("api_key", "").strip()
                status = r.get("status", "active")
                if status not in ("active", "frozen"):
                    status = "active"
                alias = r.get("alias", "") or ""
                conn.execute(
                    """INSERT INTO account_api_keys (account_id, api_key, status, alias, sort_order)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(account_id, api_key) DO UPDATE SET
                         status = excluded.status,
                         alias = excluded.alias,
                         sort_order = excluded.sort_order,
                         updated_at = CURRENT_TIMESTAMP""",
                    (account_id, key, status, alias, sort_order),
                )
            conn.commit()

    def get_active_api_keys(self, account_id: int) -> List[str]:
        """Get all active API key strings for an account."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT api_key FROM account_api_keys WHERE account_id = ? AND status = 'active' ORDER BY id",
                (account_id,),
            )
            return [row["api_key"] for row in cursor.fetchall()]

    def count_active_keys(self, account_id_str: str) -> int:
        """Count routing candidates (active keys) for an account by its string account_id (UUID).

        Mirrors ``AliasRouter._build_candidates``: every active key record in
        ``account_api_keys`` is a candidate, and the primary key from the
        ``accounts`` table is always available when not duplicated as a record.
        Returns at least 1 (the primary key). Used by the quota multiplier:
        effective ``max_requests = config_limit × N``.
        """
        acc = self.find_by_account_id(account_id_str)
        if acc is None:
            return 1
        keys = self.find_all_api_keys(acc["id"])
        return max(1, sum(1 for k in keys if k.get("status", "active") != "frozen"))

    def find_all_api_keys(self, account_id: int) -> List[dict]:
        """Get all API keys (including frozen) for an account from account_api_keys."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM account_api_keys WHERE account_id = ? ORDER BY sort_order, id",
                (account_id,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def add_api_key(self, account_id: int, api_key: str) -> dict:
        """Add a new API key for an account."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO account_api_keys (account_id, api_key, status, alias) VALUES (?, ?, 'active', '')",
                (account_id, api_key),
            )
            conn.commit()
            return self.find_api_key_by_id(cursor.lastrowid)

    def find_api_key_by_id(self, key_id: int) -> Optional[dict]:
        """Get a specific API key by its row id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM account_api_keys WHERE id = ?", (key_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_api_key_status(self, key_id: int, status: str) -> Optional[dict]:
        """Freeze or unfreeze an API key by updating its status."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE account_api_keys SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, key_id),
            )
            conn.commit()
        return self.find_api_key_by_id(key_id)

    def delete_api_key(self, key_id: int) -> bool:
        """Delete an API key."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM account_api_keys WHERE id = ?", (key_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
