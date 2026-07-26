"""Migration 013: change account_rate_windows PK to (account_id, model_name).

Supports two fixed-window modes:
- per_provider (legacy): model_name = '__global__'
- per_model: model_name = actual model name (each model has its own window)
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class ModelRateWindows(Migration):
    version = 13
    description = "Change account_rate_windows PK to (account_id, model_name)"

    def up(self, conn: sqlite3.Connection) -> None:
        # Check if the table exists with the old schema (single-column PK)
        pragma = conn.execute("PRAGMA table_info(account_rate_windows)").fetchall()
        cols = {r["name"]: r for r in pragma}
        # Old schema has account_id as PK but no model_name column
        if "model_name" in cols:
            # Already migrated — skip
            return

        conn.execute("""
            CREATE TABLE IF NOT EXISTS account_rate_windows_new (
                account_id TEXT NOT NULL,
                model_name TEXT NOT NULL DEFAULT '__global__',
                window_start TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, model_name)
            )
        """)

        conn.execute("""
            INSERT INTO account_rate_windows_new (account_id, model_name, window_start, request_count, updated_at)
            SELECT account_id, '__global__', window_start, request_count, updated_at FROM account_rate_windows
        """)

        conn.execute("DROP TABLE account_rate_windows")
        conn.execute("ALTER TABLE account_rate_windows_new RENAME TO account_rate_windows")