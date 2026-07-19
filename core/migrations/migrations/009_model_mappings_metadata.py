"""Migration 009: add description, status, created_at, updated_at to model_mappings."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class ModelMappingsMetadata(Migration):
    version = 9
    description = "Add description/status/timestamps to model_mappings"

    _COLUMNS = [
        ("description", "TEXT NOT NULL DEFAULT ''"),
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("created_at", "TEXT DEFAULT '1970-01-01 00:00:00'"),
        ("updated_at", "TEXT DEFAULT '1970-01-01 00:00:00'"),
    ]

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(model_mappings)")]
        for col_name, col_type in self._COLUMNS:
            if col_name not in cols:
                conn.execute(f"ALTER TABLE model_mappings ADD COLUMN {col_name} {col_type}")
