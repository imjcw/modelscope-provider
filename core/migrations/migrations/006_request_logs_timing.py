"""Migration 006: add timing + cached token columns to request_logs."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsTiming(Migration):
    version = 6
    description = "Add timing and cached token columns to request_logs"

    _COLUMNS = {
        "request_start": "DATETIME",
        "first_response": "DATETIME",
        "end_time": "DATETIME",
        "cached_tokens": "INTEGER DEFAULT 0",
        "prompt_partial_cached": "INTEGER DEFAULT 0",
    }

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        for col_name, col_type in self._COLUMNS.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE request_logs ADD COLUMN {col_name} {col_type}")
