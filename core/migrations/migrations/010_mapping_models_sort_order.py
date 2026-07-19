"""Migration 010: add sort_order to mapping_models."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class MappingModelsSortOrder(Migration):
    version = 10
    description = "Add sort_order to mapping_models"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(mapping_models)")]
        if "sort_order" not in cols:
            conn.execute(
                "ALTER TABLE mapping_models ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            )
