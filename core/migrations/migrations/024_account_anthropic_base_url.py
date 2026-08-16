"""Migration 024: add anthropic_base_url to accounts.

A single supplier may expose BOTH an OpenAI-compatible endpoint and an
Anthropic-native endpoint at DIFFERENT URLs. The legacy schema only stored one
``base_url`` (used for whichever protocol ``provider_type`` implied), which
could not represent a supplier whose two endpoints live on different hosts/paths.

We add a nullable ``anthropic_base_url`` column. When set it is used as the
upstream base for Anthropic-protocol requests (the ``/anthropic/v1/messages``
entry point); when unset the gateway falls back to ``base_url``. This lets one
supplier row carry both URLs.

Idempotent: no-op if the column already exists.
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountAnthropicBaseUrl(Migration):
    version = 24
    description = "Add anthropic_base_url to accounts for dual OpenAI/Anthropic endpoints"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)")}
        if "anthropic_base_url" in cols:
            return  # already applied (idempotent)
        conn.execute(
            "ALTER TABLE accounts ADD COLUMN anthropic_base_url TEXT"
        )
