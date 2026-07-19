"""Migration 007: drop region from model_mappings, enforce UNIQUE(alias_name)."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class ModelMappingsRebuild(Migration):
    version = 7
    description = "Rebuild model_mappings: drop region, enforce UNIQUE(alias_name)"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(model_mappings)")]
        if "region" not in cols:
            # Modern schema (no region). UNIQUE(alias_name) is enforced by the
            # rebuilt table in this migration's region path; nothing to do here.
            return

        # Legacy schema with region → rebuild
        conn.execute("""
            CREATE TABLE model_mappings_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias_name TEXT NOT NULL UNIQUE,
                actual_model_id TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO model_mappings_new (alias_name, actual_model_id)
            SELECT alias_name, actual_model_id
            FROM model_mappings
            WHERE id IN (SELECT MIN(id) FROM model_mappings GROUP BY alias_name)
        """)
        conn.execute("DROP TABLE model_mappings")
        conn.execute("ALTER TABLE model_mappings_new RENAME TO model_mappings")
