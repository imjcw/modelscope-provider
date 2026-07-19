"""Migration 003: add name column to accounts + create unique index."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountsName(Migration):
    version = 3
    description = "Add name column to accounts with unique index"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "name" not in cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN name TEXT NOT NULL DEFAULT ''")
            conn.execute("UPDATE accounts SET name = account_id WHERE name = ''")
        # Idempotent — CREATE UNIQUE INDEX IF NOT EXISTS is safe to re-run
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name)"
        )
