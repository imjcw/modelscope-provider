"""Migration 001: add total_input_tokens and total_output_tokens to account_quotas."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountQuotasTokens(Migration):
    version = 1
    description = "Add total_input_tokens and total_output_tokens to account_quotas"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(account_quotas)")]
        if "total_input_tokens" not in cols:
            conn.execute(
                "ALTER TABLE account_quotas ADD COLUMN total_input_tokens INTEGER NOT NULL DEFAULT 0"
            )
        if "total_output_tokens" not in cols:
            conn.execute(
                "ALTER TABLE account_quotas ADD COLUMN total_output_tokens INTEGER NOT NULL DEFAULT 0"
            )
