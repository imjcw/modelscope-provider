"""Tests for individual migration classes."""

import sqlite3
import pytest
from core.database import DatabaseManager
from core.migrations.registry import clear_registry, get_all_migrations, register

# The migrations package (__init__.py) auto-imports submodule modules solely to fire
# their @register decorators; it does not re-export the class names. Pull the classes
# from the registry — the same API the Migrator uses. clear_registry first, then import
# the package to trigger registration of all on-disk migrations. get_all_migrations()
# returns sorted instances; take their classes so the body can do `Cls().up(conn)`.
clear_registry()
import core.migrations.migrations  # noqa: E402,F401  # triggers @register for all versioned migrations
AccountQuotasTokens, RequestLogsResponseHeaders, RequestLogsClientKeyName = [
    type(m) for m in get_all_migrations()
]


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
