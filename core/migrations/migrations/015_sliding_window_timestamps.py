"""Migration 015: add timestamps column to account_rate_windows.

Sliding-window rate limiting (see ``services/cache.RateLimitWindow``) needs to
persist the per-request timestamps so the window can be reconstructed exactly
after a restart, instead of only storing a single ``window_start`` +
``request_count`` pair.
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class SlidingWindowTimestamps(Migration):
    version = 15
    description = "Add timestamps column to account_rate_windows for sliding-window counting"

    def up(self, conn: sqlite3.Connection) -> None:
        pragma = conn.execute("PRAGMA table_info(account_rate_windows)").fetchall()
        cols = {r["name"] for r in pragma}
        if "timestamps" not in cols:
            conn.execute(
                "ALTER TABLE account_rate_windows ADD COLUMN timestamps TEXT"
            )
