"""Migration 018: create account_api_keys table for multi-key support."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountApiKeys(Migration):
    version = 18
    description = "Create account_api_keys table for multiple API keys per supplier"

    def up(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS account_api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                api_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, api_key)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_api_keys_account_id
            ON account_api_keys(account_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_account_api_keys_status
            ON account_api_keys(status)
        """)
