"""Migration 020: add sort_order column to account_api_keys for user-defined key order."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountApiKeysSortOrder(Migration):
    version = 20
    description = "Add sort_order column to account_api_keys for user-defined key order"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(account_api_keys)")]
        if "sort_order" not in cols:
            conn.execute("""
                ALTER TABLE account_api_keys ADD COLUMN sort_order INTEGER DEFAULT 0
            """)
            # Backfill: assign sort_order based on existing id order
            conn.execute("""
                UPDATE account_api_keys
                SET sort_order = seq
                FROM (SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS seq
                      FROM account_api_keys)
                WHERE account_api_keys.id = seq
            """)
