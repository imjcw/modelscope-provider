"""Migration 026: add key_id to account_quotas.

The supplier-level daily quota (header_based / ModelScope) was keyed by
``(account_id, quota_date)`` and therefore shared across all of a supplier's API
keys. Each key is an independent ModelScope account with its own upstream quota,
so the row must be keyed by ``(account_id, key_id, quota_date)`` — i.e. per key.

SenseTime uses ``key_id = 0`` (single supplier-wide row), so its behaviour is
unchanged by this change.
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountQuotasKeyId(Migration):
    version = 26
    description = (
        "Add key_id column to account_quotas and key by "
        "(account_id, key_id, quota_date)"
    )

    def up(self, conn: sqlite3.Connection) -> None:
        pragma = conn.execute("PRAGMA table_info(account_quotas)").fetchall()
        cols = {r["name"] for r in pragma}
        if "key_id" in cols:
            return  # already migrated (idempotent)

        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='account_quotas'"
        ).fetchone()
        if not table_exists:
            return

        # Rebuild to change the PRIMARY KEY. Legacy rows had a single
        # (account_id, quota_date) counter (one shared key); dedupe them onto
        # key_id = 0 so the new PK stays unique while preserving the count.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_quotas_new (
                account_id TEXT NOT NULL,
                quota_date TEXT NOT NULL,
                key_id INTEGER NOT NULL DEFAULT 0,
                quota_remaining INTEGER NOT NULL DEFAULT 0,
                quota_limit INTEGER NOT NULL DEFAULT 0,
                total_input_tokens INTEGER NOT NULL DEFAULT 0,
                total_output_tokens INTEGER NOT NULL DEFAULT 0,
                unavailable_models TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, key_id, quota_date)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO account_quotas_new
                (account_id, quota_date, key_id, quota_remaining, quota_limit,
                 total_input_tokens, total_output_tokens, unavailable_models)
            SELECT account_id, quota_date, 0,
                   MAX(quota_remaining), MAX(quota_limit),
                   MAX(total_input_tokens), MAX(total_output_tokens),
                   MAX(unavailable_models)
            FROM account_quotas
            GROUP BY account_id, quota_date
            """
        )
        conn.execute("DROP TABLE account_quotas")
        conn.execute(
            "ALTER TABLE account_quotas_new RENAME TO account_quotas"
        )
