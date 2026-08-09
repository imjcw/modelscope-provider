"""Change provider_type column default from 'modelscope' to '' (empty = no restrictions)."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class ProviderTypeEmptyDefault(Migration):
    version = 17
    description = "Change provider_type column default from 'modelscope' to ''"

    def up(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                provider_type TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO accounts_new (id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at)
            SELECT id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at
            FROM accounts
        """)
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts (account_id)"
        )

    def down(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                provider_type TEXT NOT NULL DEFAULT 'modelscope',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO accounts_new (id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at)
            SELECT id, account_id, name, api_key, base_url, provider_type, status, created_at, updated_at
            FROM accounts
        """)
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts (account_id)"
        )
