"""Migration 011: add provider_type to accounts; create account_rate_windows."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountsProviderType(Migration):
    version = 11
    description = "Add provider_type to accounts and create account_rate_windows table"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "provider_type" not in cols:
            conn.execute(
                "ALTER TABLE accounts ADD COLUMN provider_type TEXT NOT NULL DEFAULT 'modelscope'"
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS account_rate_windows (
                account_id TEXT PRIMARY KEY,
                window_start TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
