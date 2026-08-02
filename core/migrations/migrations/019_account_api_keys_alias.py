"""Migration 019: add alias column to account_api_keys table."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountApiKeysAlias(Migration):
    version = 19
    description = "Add alias column to account_api_keys for key display names"

    def up(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            ALTER TABLE account_api_keys ADD COLUMN alias TEXT DEFAULT ''
        """)
