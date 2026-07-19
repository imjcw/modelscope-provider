"""Migration 008: add client_key_name to request_logs."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsClientKeyName(Migration):
    version = 8
    description = "Add client_key_name to request_logs"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        if "client_key_name" not in cols:
            conn.execute("ALTER TABLE request_logs ADD COLUMN client_key_name TEXT")
