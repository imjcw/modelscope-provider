"""Migration 002: add response_headers to request_logs."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsResponseHeaders(Migration):
    version = 2
    description = "Add response_headers to request_logs"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        if "response_headers" not in cols:
            conn.execute("ALTER TABLE request_logs ADD COLUMN response_headers TEXT")
