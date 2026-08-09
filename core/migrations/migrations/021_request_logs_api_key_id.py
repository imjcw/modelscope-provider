"""Migration 021: add api_key_id column to request_logs for key-level auditing.

Before this migration, the request_logs table only recorded ``account_id``,
so the admin panel could not tell which API key was used for a particular
request. Adding ``api_key_id`` makes it possible to trace key-level failures
and usage patterns.

``api_key_id`` is the ``account_api_keys.id`` (0 = primary key from the
accounts table, which is the default for legacy log entries).
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsApiKeyId(Migration):
    version = 21
    description = "Add api_key_id column to request_logs for key-level auditing"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        if "api_key_id" not in cols:
            conn.execute("""
                ALTER TABLE request_logs ADD COLUMN api_key_id INTEGER DEFAULT 0
            """)