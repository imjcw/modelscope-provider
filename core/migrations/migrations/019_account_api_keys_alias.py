"""Migration 019: add alias column to account_api_keys table."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountApiKeysAlias(Migration):
    version = 19
    description = "Add alias column to account_api_keys for key display names"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(account_api_keys)")]
        if "alias" in cols:
            return  # already present (e.g. created by initialize_tables)
        conn.execute("""
            ALTER TABLE account_api_keys ADD COLUMN alias TEXT DEFAULT ''
        """)
