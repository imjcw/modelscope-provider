"""Migration 005: drop region column from accounts (table rebuild)."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountsDropRegion(Migration):
    version = 5
    description = "Drop region column from accounts"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "region" not in cols:
            return  # already removed

        # Rebuilding the parent `accounts` table via DROP TABLE cascades to child
        # tables under PRAGMA foreign_keys=ON. Disable FK for the rebuild.
        try:
            conn.commit()
        except Exception:
            pass
        conn.execute("PRAGMA foreign_keys = OFF")

        # SQLite < 3.35 doesn't support DROP COLUMN → rebuild.
        # Carry over only columns that exist in the source (don't assume name/status
        # are present in every legacy schema), and never carry region.
        target = ["id", "account_id", "api_key", "base_url", "status", "name", "created_at", "updated_at"]
        keep = [c for c in target if c in cols]
        keep_list = ", ".join(keep)
        conn.execute("""
            CREATE TABLE accounts_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL UNIQUE,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                name TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(f"""
            INSERT INTO accounts_new ({keep_list})
            SELECT {keep_list} FROM accounts
        """)
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
        # Preserve unique index on name
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name)"
        )
        # Restore FK enforcement for subsequent operations.
        conn.execute("PRAGMA foreign_keys = ON")
