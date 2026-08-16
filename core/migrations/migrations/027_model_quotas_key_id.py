"""Migration 027: add key_id to model_quotas.

``model_quotas`` was keyed by ``(account_id, model_name, quota_date)`` and shared
across all of a supplier's API keys. Each key is an independent ModelScope account
with its own upstream quota, so the row must be keyed by
``(account_id, model_name, key_id, quota_date)`` — per key, per model, per day.

Legacy rows are migrated onto ``key_id = 0`` (primary key).
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class ModelQuotasKeyId(Migration):
    version = 27
    description = (
        "Add key_id column to model_quotas and key by "
        "(account_id, model_name, key_id, quota_date)"
    )

    def up(self, conn: sqlite3.Connection) -> None:
        pragma = conn.execute("PRAGMA table_info(model_quotas)").fetchall()
        cols = {r["name"] for r in pragma}
        if "key_id" in cols:
            return  # already migrated (idempotent)

        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='model_quotas'"
        ).fetchone()
        if not table_exists:
            return

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_quotas_new (
                account_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                key_id INTEGER NOT NULL DEFAULT 0,
                quota_date TEXT NOT NULL,
                quota_remaining INTEGER NOT NULL DEFAULT 0,
                quota_limit INTEGER NOT NULL DEFAULT 0,
                total_input_tokens INTEGER NOT NULL DEFAULT 0,
                total_output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, model_name, key_id, quota_date)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO model_quotas_new
                (account_id, model_name, key_id, quota_date,
                 quota_remaining, quota_limit,
                 total_input_tokens, total_output_tokens)
            SELECT account_id, model_name, 0, quota_date,
                   MAX(quota_remaining), MAX(quota_limit),
                   MAX(total_input_tokens), MAX(total_output_tokens)
            FROM model_quotas
            GROUP BY account_id, model_name, quota_date
            """
        )
        conn.execute("DROP TABLE model_quotas")
        conn.execute(
            "ALTER TABLE model_quotas_new RENAME TO model_quotas"
        )