"""Migration 025: add key_id to account_rate_windows.

The fixed-window rate-limit counter for the ``fixed_window_per_model`` strategy
was keyed by ``(account_id, model_name)`` and therefore shared across ALL API
keys of a supplier. When a supplier has multiple keys, each key holds its own
upstream quota, so the window must be keyed by ``(account_id, model_name,
key_id)`` — i.e. per key+model.

SenseTime (``fixed_window``) intentionally keeps a single supplier-wide
counter; it always writes/reads with ``key_id = 0``, so its behaviour is
unchanged by this change.
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountRateWindowsKeyId(Migration):
    version = 25
    description = (
        "Add key_id column to account_rate_windows and key window by "
        "(account_id, model_name, key_id)"
    )

    def up(self, conn: sqlite3.Connection) -> None:
        pragma = conn.execute("PRAGMA table_info(account_rate_windows)").fetchall()
        cols = {r["name"] for r in pragma}
        if "key_id" in cols:
            return  # already migrated (idempotent)

        # The table may not exist at all on a database bootstrapped before the
        # account_rate_windows table was introduced; earlier migration 011 will
        # (re)create it with the new schema, so there's nothing to rebuild here.
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='account_rate_windows'"
        ).fetchone()
        if not table_exists:
            return

        # Rebuild the table to change the PRIMARY KEY. Legacy rows used a single
        # (account_id, model_name) counter (one key); dedupe them onto key_id = 0
        # so the new PK stays unique while preserving the historical count.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_rate_windows_new (
                account_id  TEXT    NOT NULL,
                model_name  TEXT    NOT NULL DEFAULT '__global__',
                key_id      INTEGER NOT NULL DEFAULT 0,
                window_start TEXT   NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                timestamps  TEXT,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, model_name, key_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO account_rate_windows_new
                (account_id, model_name, key_id, window_start,
                 request_count, timestamps, updated_at)
            SELECT account_id, model_name, 0,
                   MAX(window_start), MAX(request_count),
                   MAX(timestamps), MAX(updated_at)
            FROM account_rate_windows
            GROUP BY account_id, model_name
            """
        )
        conn.execute("DROP TABLE account_rate_windows")
        conn.execute(
            "ALTER TABLE account_rate_windows_new RENAME TO account_rate_windows"
        )
