"""Migration 014: replace mapping_models.model_name with supplier_model_id FK.

Maps each binding to supplier_models.id instead of a string snapshot of the
model name.  When a supplier renames or deletes a model the binding no longer
goes stale — it follows the id (and CASCADE deletes orphan bindings).

Steps:
  1. ADD COLUMN supplier_model_id INTEGER (nullable during migration).
  2. Backfill supplier_model_id by looking up (supplier_id, model_name).
  3. Rebuild the table so we can: drop model_name, add the FK, change the
     UNIQUE constraint to (alias_name, supplier_model_id).
"""

import logging
import sqlite3

from core.migrations.base import Migration
from core.migrations.registry import register

logger = logging.getLogger(__name__)


@register
class MappingModelsSupplierFk(Migration):
    version = 14
    description = "Replace mapping_models.model_name with supplier_model_id FK"

    def up(self, conn: sqlite3.Connection) -> None:
        # supplier_models is required for the FK; create it if absent
        # (it's in the base schema, but may not exist on very old upgrades).
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "supplier_models" not in tables:
            conn.execute("""
                CREATE TABLE supplier_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    context_length INTEGER,
                    UNIQUE(supplier_id, model_name)
                )
            """)

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(mapping_models)")}
        if "supplier_model_id" in cols and "model_name" not in cols:
            logger.info("Migration 014: already applied")
            return

        # ── 1. Add nullable column (for tables where model_name still exists) ──
        if "supplier_model_id" not in cols:
            conn.execute(
                "ALTER TABLE mapping_models ADD COLUMN supplier_model_id INTEGER"
            )

        # ── 2. Backfill from existing (supplier_id, model_name) pairs ──
        backfilled = 0
        missing = 0
        for row in conn.execute(
            """SELECT mm.id, mm.supplier_id, mm.model_name
               FROM mapping_models mm
               WHERE mm.supplier_model_id IS NULL AND mm.model_name IS NOT NULL"""
        ):
            mm_id, supplier_id, model_name = row
            match = conn.execute(
                "SELECT id FROM supplier_models WHERE supplier_id = ? AND model_name = ?",
                (supplier_id, model_name),
            ).fetchone()
            if match:
                conn.execute(
                    "UPDATE mapping_models SET supplier_model_id = ? WHERE id = ?",
                    (match["id"], mm_id),
                )
                backfilled += 1
            else:
                missing += 1
                logger.warning(
                    "Migration 014: no supplier_models match for "
                    "mapping_models id=%d supplier_id=%d model_name=%s — "
                    "binding will be removed on rebuild",
                    mm_id, supplier_id, model_name,
                )

        logger.info(
            "Migration 014: backfilled %d, dropped %d unmatched bindings",
            backfilled, missing,
        )

        # ── 3. Rebuild table to drop model_name, add FK, fix UNIQUE ──
        conn.execute("""
            CREATE TABLE mapping_models_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias_name TEXT NOT NULL,
                supplier_model_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alias_name) REFERENCES model_mappings(alias_name) ON DELETE CASCADE,
                FOREIGN KEY (supplier_model_id) REFERENCES supplier_models(id) ON DELETE CASCADE,
                UNIQUE(alias_name, supplier_model_id)
            )
        """)

        # Carry over only rows with a valid supplier_model_id.
        # Build a dynamic INSERT because legacy tables may be missing
        # created_at / updated_at / sort_order.
        old_cols = {r["name"] for r in conn.execute("PRAGMA table_info(mapping_models)")}
        _carry_cols = ["id", "alias_name", "supplier_model_id"]
        if "sort_order" in old_cols:
            _carry_cols.append("sort_order")
        if "created_at" in old_cols:
            _carry_cols.append("created_at")
        if "updated_at" in old_cols:
            _carry_cols.append("updated_at")
        _carry_list = ", ".join(_carry_cols)
        conn.execute(
            f"""INSERT INTO mapping_models_new ({_carry_list})
                SELECT {_carry_list} FROM mapping_models
                WHERE supplier_model_id IS NOT NULL"""
        )

        conn.execute("DROP TABLE mapping_models")
        conn.execute("ALTER TABLE mapping_models_new RENAME TO mapping_models")

        # Re-add indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mapping_models_alias ON mapping_models(alias_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mapping_models_supplier_model_id "
            "ON mapping_models(supplier_model_id)"
        )
        logger.info("Migration 014: completed")

    def down(self, conn: sqlite3.Connection) -> None:
        """Revert to model_name column (best-effort)."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(mapping_models)")}
        if "model_name" in cols:
            logger.info("Migration 014 down: model_name already present")
            return

        # Rebuild, restoring model_name from supplier_models JOIN.
        conn.execute("""
            CREATE TABLE mapping_models_old (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias_name TEXT NOT NULL,
                supplier_id INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alias_name) REFERENCES model_mappings(alias_name) ON DELETE CASCADE,
                FOREIGN KEY (supplier_id) REFERENCES accounts(id) ON DELETE CASCADE,
                UNIQUE(alias_name, supplier_id, model_name)
            )
        """)
        conn.execute("""
            INSERT INTO mapping_models_old
                (id, alias_name, supplier_id, model_name, sort_order, created_at, updated_at)
            SELECT mm.id, mm.alias_name, sm.supplier_id, sm.model_name,
                   mm.sort_order, mm.created_at, mm.updated_at
            FROM mapping_models mm
            JOIN supplier_models sm ON sm.id = mm.supplier_model_id
        """)
        conn.execute("DROP TABLE mapping_models")
        conn.execute("ALTER TABLE mapping_models_old RENAME TO mapping_models")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mapping_models_alias ON mapping_models(alias_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mapping_models_supplier ON mapping_models(supplier_id)"
        )
