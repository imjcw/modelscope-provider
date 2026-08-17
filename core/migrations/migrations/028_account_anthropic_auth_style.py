"""Migration 028: add anthropic_auth_style to accounts.

A dual-protocol supplier may expose an Anthropic-compatible ``/v1/messages``
endpoint, but not all of them speak *native* Anthropic authentication. Native
Anthropic uses ``x-api-key``; some providers (e.g. SenseTime / 商汤) expose an
Anthropic-shaped ``/v1/messages`` yet still require ``Authorization: Bearer``.

We add a nullable ``anthropic_auth_style`` column (default ``"anthropic"``) so
the gateway can choose the auth scheme per supplier when calling its
Anthropic endpoint, instead of always forcing ``x-api-key``.

Idempotent: no-op if the column already exists.
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountAnthropicAuthStyle(Migration):
    version = 28
    description = "Add anthropic_auth_style to accounts (per-supplier Anthropic auth scheme)"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)")}
        if "anthropic_auth_style" in cols:
            return  # already applied (idempotent)
        conn.execute(
            "ALTER TABLE accounts ADD COLUMN anthropic_auth_style TEXT DEFAULT 'anthropic'"
        )
