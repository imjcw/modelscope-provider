"""Integration tests: full migration flow end-to-end."""

import pytest
from pathlib import Path
from core.database import DatabaseManager
from core.migrations import Migrator, get_all_migrations


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(f"sqlite:///{tmp_path}/test.db")


class TestFreshInstall:
    """Migrator.run() on a fresh database should record all versions."""

    def test_all_migrations_recorded(self, db):
        db.initialize_tables()
        migrator = Migrator(db)
        migrator.run()

        status = migrator.status()
        assert len(status) == 15
        assert all(s["applied"] for s in status)

    def test_idempotent_on_fresh_install(self, db):
        db.initialize_tables()
        migrator = Migrator(db)
        migrator.run()
        migrator.run()  # second run no-op

        status = migrator.status()
        assert len(status) == 15
        assert all(s["applied"] for s in status)


class TestOldDatabaseUpgrade:
    """Migrator upgrades a simulated old database (schema before migration system)."""

    def test_upgrades_fully(self, db):
        # Simulate an old database by manually creating tables with minimal schema
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
            conn.execute("""
                CREATE TABLE request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    account_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    model TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE model_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL UNIQUE,
                    actual_model_id TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE mapping_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    UNIQUE(alias_name, supplier_id, model_name)
                )
            """)

        migrator = Migrator(db)
        migrator.run()

        status = migrator.status()
        assert len(status) == 15
        assert all(s["applied"] for s in status)

        # Verify the schema was actually upgraded
        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(account_quotas)")]
            assert "total_input_tokens" in cols
            assert "total_output_tokens" in cols

            cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
            assert "name" in cols

            cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
            assert "account_name" in cols
            assert "response_headers" in cols
            assert "client_key_name" in cols


class TestMigrationCount:
    def test_thirteen_plus_one_migrations_registered(self):
        migrations = get_all_migrations()
        assert len(migrations) == 15
        versions = [m.version for m in migrations]
        assert versions == list(range(1, 16))
