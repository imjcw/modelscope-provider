"""Migration 023: migrate accounts.api_key into account_api_keys and drop the column.

Before multi-key support, each supplier stored a single primary key in the
``accounts.api_key`` column. With the ``account_api_keys`` table now the source
of truth, we:

1. Copy every non-empty ``accounts.api_key`` into ``account_api_keys`` (as the
   primary key record, alias "主密钥") — but only if that exact key isn't
   already present for the account (idempotent).
2. Drop the deprecated ``accounts.api_key`` column.

After this migration the ``accounts`` table no longer holds a key; routing and
request serving derive the primary key from ``account_api_keys``.

``DROP COLUMN`` requires SQLite >= 3.35.0. The bundled SQLite in modern Python
satisfies this; if it doesn't, we fall back to rebuilding the table without the
column.
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountDropApiKey(Migration):
    version = 23
    description = "Migrate accounts.api_key into account_api_keys and drop the column"

    def _sqlite_supports_drop_column(self, conn: sqlite3.Connection) -> bool:
        # PRAGMA table_info is always available; the real capability check is the
        # actual DROP attempt, but we also guard with the version to choose path.
        try:
            version = conn.execute("SELECT sqlite_version()").fetchone()[0]
            major, minor, patch = (int(x) for x in version.split("."))
            return (major, minor) >= (3, 35)
        except Exception:
            return False

    def _drop_column(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "api_key" not in cols:
            return  # already dropped (idempotent)

        if self._sqlite_supports_drop_column(conn):
            conn.execute("ALTER TABLE accounts DROP COLUMN api_key")
            return

        # Fallback for old SQLite: rebuild the table without the column.
        # `accounts` is the PARENT of account_api_keys / supplier_models /
        # mapping_models FKs, so disable FK first to avoid cascade-deleting them.
        try:
            conn.commit()
        except Exception:
            pass
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("CREATE TABLE accounts_new AS SELECT "
                     "id, account_id, name, base_url, provider_type, status, "
                     "created_at, updated_at FROM accounts")
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
        # Recreate the usual indexes/constraints if any existed on accounts.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS "
                     "idx_accounts_account_id ON accounts(account_id)")
        conn.execute("PRAGMA foreign_keys = ON")

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "api_key" not in cols:
            # Fresh database created without the column (see core/database.py).
            # Nothing to migrate or drop — idempotent no-op.
            return

        # 1. Migrate existing primary keys into account_api_keys.
        rows = conn.execute(
            "SELECT id, api_key FROM accounts "
            "WHERE api_key IS NOT NULL AND api_key != ''"
        ).fetchall()
        for row in rows:
            account_id = row["id"]
            key = row["api_key"]
            existing = conn.execute(
                "SELECT 1 FROM account_api_keys "
                "WHERE account_id = ? AND api_key = ?",
                (account_id, key),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO account_api_keys "
                "(account_id, api_key, status, alias, sort_order) "
                "VALUES (?, ?, 'active', '主密钥', 0)",
                (account_id, key),
            )

        # 2. Drop the now-deprecated column.
        self._drop_column(conn)
