"""Migration 004: add account_name to request_logs with backfill from accounts."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsAccountName(Migration):
    version = 4
    description = "Add account_name to request_logs with backfill"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        if "account_name" not in cols:
            conn.execute("ALTER TABLE request_logs ADD COLUMN account_name TEXT")
            conn.execute(
                """UPDATE request_logs SET account_name =
                   (SELECT name FROM accounts WHERE accounts.account_id = request_logs.account_id)
                   WHERE account_name IS NULL"""
            )
