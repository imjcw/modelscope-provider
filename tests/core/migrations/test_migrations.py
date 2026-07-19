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
AccountQuotasTokens, RequestLogsResponseHeaders, AccountsName, RequestLogsAccountName, RequestLogsClientKeyName = [
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
