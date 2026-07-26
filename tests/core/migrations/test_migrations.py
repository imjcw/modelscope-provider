"""Tests for individual migration classes."""

import sqlite3
import pytest
from core.database import DatabaseManager
from core.migrations.registry import get_all_migrations

# The migrations package (__init__.py) auto-imports the submodule to fire each
# migration's @register decorator, so the global registry is fully populated on
# import. Pull the classes from the registry — the same API the Migrator uses.
# get_all_migrations() returns sorted instances; take their classes so the body
# can do `Cls().up(conn)`.
by_version = {m.version: type(m) for m in get_all_migrations()}
# Named aliases pinned by version for the existing tests below (bodies left unchanged).
AccountQuotasTokens = by_version[1]
RequestLogsResponseHeaders = by_version[2]
AccountsName = by_version[3]
RequestLogsAccountName = by_version[4]
RequestLogsClientKeyName = by_version[8]


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(f"sqlite:///{tmp_path}/test.db")


class TestMigration001_AccountQuotasTokens:
    def test_adds_columns(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE account_quotas (
                    account_id TEXT NOT NULL,
                    quota_date TEXT NOT NULL,
                    quota_remaining INTEGER NOT NULL DEFAULT 0,
                    quota_limit INTEGER NOT NULL DEFAULT 0,
                    unavailable_models TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, quota_date)
                )
            """)

        with db.get_connection() as conn:
            AccountQuotasTokens().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(account_quotas)")]
            assert "total_input_tokens" in cols
            assert "total_output_tokens" in cols

    def test_idempotent(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE account_quotas (
                    account_id TEXT NOT NULL, quota_date TEXT NOT NULL,
                    quota_remaining INTEGER NOT NULL DEFAULT 0,
                    quota_limit INTEGER NOT NULL DEFAULT 0,
                    unavailable_models TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, quota_date)
                )
            """)

        with db.get_connection() as conn:
            AccountQuotasTokens().up(conn)
            AccountQuotasTokens().up(conn)  # second call no-op

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(account_quotas)")]
            assert cols.count("total_input_tokens") == 1


class TestMigration002_ResponseHeaders:
    def test_adds_column(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE request_logs (id INTEGER PRIMARY KEY, ts DATETIME)
            """)

        with db.get_connection() as conn:
            RequestLogsResponseHeaders().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
            assert "response_headers" in cols


class TestMigration008_ClientKeyName:
    def test_adds_column(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE request_logs (id INTEGER PRIMARY KEY, ts DATETIME)
            """)

        with db.get_connection() as conn:
            RequestLogsClientKeyName().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
            assert "client_key_name" in cols


class TestMigration003_AccountsName:
    def test_adds_column_and_index(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL UNIQUE,
                    api_key TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO accounts (account_id, api_key, base_url) VALUES ('acc-1', 'key', 'url')"
            )

        with db.get_connection() as conn:
            AccountsName().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
            assert "name" in cols
            # Verify backfill
            name = conn.execute("SELECT name FROM accounts WHERE account_id = 'acc-1'").fetchone()[0]
            assert name == "acc-1"
            # Verify index exists
            indexes = [r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='accounts'"
            )]
            assert "idx_accounts_name" in indexes


class TestMigration004_RequestLogsAccountName:
    def test_adds_column_and_backfills(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    api_key TEXT NOT NULL,
                    base_url TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE request_logs (
                    id INTEGER PRIMARY KEY,
                    account_id TEXT
                )
            """)
            conn.execute(
                "INSERT INTO accounts (account_id, name, api_key, base_url) VALUES ('acc-1', 'MyAccount', 'key', 'url')"
            )
            conn.execute(
                "INSERT INTO request_logs (account_id) VALUES ('acc-1')"
            )

        with db.get_connection() as conn:
            RequestLogsAccountName().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
            assert "account_name" in cols
            name = conn.execute("SELECT account_name FROM request_logs LIMIT 1").fetchone()[0]
            assert name == "MyAccount"


class TestMigration005_AccountsDropRegion:
    def test_drops_region_column(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL UNIQUE,
                    api_key TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    region TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO accounts (account_id, api_key, base_url, region) VALUES ('a1', 'k', 'u', 'us')"
            )

        with db.get_connection() as conn:
            by_version[5]().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
            assert "region" not in cols
            # Data preserved
            row = conn.execute("SELECT account_id FROM accounts").fetchone()
            assert row[0] == "a1"


class TestMigration006_RequestLogsTiming:
    def test_adds_all_timing_columns(self, db):
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE request_logs (id INTEGER PRIMARY KEY)")

        with db.get_connection() as conn:
            by_version[6]().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
            for expected in ("request_start", "first_response", "end_time", "cached_tokens", "prompt_partial_cached"):
                assert expected in cols


class TestMigration007_ModelMappingsRebuild:
    def test_fixes_unique_constraint(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE model_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL,
                    actual_model_id TEXT NOT NULL,
                    region TEXT
                )
            """)

        with db.get_connection() as conn:
            by_version[7]().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(model_mappings)")]
            assert "region" not in cols


class TestMigration009_ModelMappingsMetadata:
    def test_adds_metadata_columns(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE model_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL UNIQUE,
                    actual_model_id TEXT NOT NULL
                )
            """)

        with db.get_connection() as conn:
            by_version[9]().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(model_mappings)")]
            for expected in ("description", "status", "created_at", "updated_at"):
                assert expected in cols


class TestMigration010_MappingModelsSortOrder:
    def test_adds_sort_order(self, db):
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE mapping_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    UNIQUE(alias_name, supplier_id, model_name)
                )
            """)

        with db.get_connection() as conn:
            by_version[10]().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(mapping_models)")]
            assert "sort_order" in cols


class TestMigration014_MappingModelsSupplierFk:
    def test_replaces_model_name_with_supplier_model_id(self, db):
        """Migration 014 adds supplier_model_id, backfills from model_name, drops model_name."""
        with db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE model_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL UNIQUE
                )
            """)
            conn.execute("""
                CREATE TABLE supplier_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    UNIQUE(supplier_id, model_name)
                )
            """)
            conn.execute("""
                CREATE TABLE mapping_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(alias_name, supplier_id, model_name)
                )
            """)
            # Insert supplier_models so backfill can resolve them
            conn.execute(
                "INSERT INTO supplier_models (id, supplier_id, model_name, model_type) VALUES (1, 1, 'qwen-max', 'text')"
            )
            conn.execute(
                "INSERT INTO model_mappings (alias_name) VALUES ('my-alias')"
            )
            conn.execute(
                "INSERT INTO mapping_models (id, alias_name, supplier_id, model_name, sort_order) VALUES (1, 'my-alias', 1, 'qwen-max', 0)"
            )

        with db.get_connection() as conn:
            by_version[14]().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(mapping_models)")]
            assert "supplier_model_id" in cols
            assert "model_name" not in cols
            # Backfill worked
            row = conn.execute(
                "SELECT supplier_model_id FROM mapping_models WHERE alias_name = 'my-alias'"
            ).fetchone()
            assert row[0] == 1
