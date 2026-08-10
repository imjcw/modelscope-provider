"""Change provider_type column default from 'modelscope' to '' (empty = no restrictions)."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class ProviderTypeEmptyDefault(Migration):
    version = 17
    description = "Change provider_type column default from 'modelscope' to ''"

    def up(self, conn):
        # Rebuilding the parent `accounts` table via DROP TABLE fires an implicit
        # DELETE under PRAGMA foreign_keys=ON, cascading via ON DELETE CASCADE to
        # account_api_keys / supplier_models / mapping_models and wiping them.
        # Disable FK for the rebuild so all child rows survive, then restore it.
        try:
            conn.commit()
        except Exception:
            pass
        conn.execute("PRAGMA foreign_keys = OFF")

        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        # Preserve api_key column if it still exists — migration 023 is responsible
        # for migrating its data into account_api_keys and dropping it. If v17
        # removes it first, v23 can't find it and all keys are lost silently.
        api_key_col = "api_key TEXT NOT NULL DEFAULT ''," if "api_key" in cols else ""
        conn.execute(
            "CREATE TABLE accounts_new ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "account_id TEXT NOT NULL UNIQUE,"
            f"name TEXT NOT NULL DEFAULT '',{api_key_col}"
            "base_url TEXT NOT NULL,"
            "provider_type TEXT NOT NULL DEFAULT '',"
            "status TEXT NOT NULL DEFAULT 'active',"
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        select_cols = (
            "id, account_id, name, api_key, base_url, "
            "provider_type, status, created_at, updated_at"
            if "api_key" in cols else
            "id, account_id, name, base_url, "
            "provider_type, status, created_at, updated_at"
        )
        conn.execute(
            f"INSERT INTO accounts_new ({select_cols}) SELECT {select_cols} FROM accounts"
        )
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts (account_id)"
        )
        # Restore FK enforcement for subsequent operations.
        conn.execute("PRAGMA foreign_keys = ON")

    def down(self, conn):
        # Same FK-off guard as up(): rebuilding the parent `accounts` table must
        # not cascade-delete child rows.
        try:
            conn.commit()
        except Exception:
            pass
        conn.execute("PRAGMA foreign_keys = OFF")

        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        api_key_col = "api_key TEXT NOT NULL DEFAULT ''," if "api_key" in cols else ""
        conn.execute(
            "CREATE TABLE accounts_new ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "account_id TEXT NOT NULL UNIQUE,"
            f"name TEXT NOT NULL DEFAULT '',{api_key_col}"
            "base_url TEXT NOT NULL,"
            "provider_type TEXT NOT NULL DEFAULT 'modelscope',"
            "status TEXT NOT NULL DEFAULT 'active',"
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        select_cols = (
            "id, account_id, name, api_key, base_url, "
            "provider_type, status, created_at, updated_at"
            if "api_key" in cols else
            "id, account_id, name, base_url, "
            "provider_type, status, created_at, updated_at"
        )
        conn.execute(
            f"INSERT INTO accounts_new ({select_cols}) SELECT {select_cols} FROM accounts"
        )
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts (account_id)"
        )
        # Restore FK enforcement for subsequent operations.
        conn.execute("PRAGMA foreign_keys = ON")
