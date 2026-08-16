import sqlite3

import pytest
from provider.core.database import DatabaseManager


def test_database_initialization(database):
    """Test that database tables are created successfully."""
    date_str = database.get_today_date()
    assert date_str is not None

    # Verify both tables actually exist in the database
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('account_quotas', 'model_alias_cache')"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "account_quotas" in tables
        assert "model_alias_cache" in tables


def test_get_today_date(database):
    """Test date format."""
    date_str = database.get_today_date()
    assert len(date_str) == 10
    assert date_str.startswith("20")


def test_account_quotas_composite_primary_key(database):
    """Verify account_quotas uses a composite primary key on (account_id, key_id, quota_date)."""
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(account_quotas)")
        columns = {row[1]: row for row in cursor.fetchall()}

        pk_columns = [name for name, row in columns.items() if row[5] > 0]
        assert set(pk_columns) == {"account_id", "key_id", "quota_date"}


def test_account_quotas_duplicate_rejection(database):
    """Verify that duplicate (account_id, key_id, quota_date) rows are rejected."""
    with database.get_connection() as conn:
        cursor = conn.cursor()
        today = database.get_today_date()
        cursor.execute(
            "INSERT INTO account_quotas (account_id, key_id, quota_date, quota_remaining, quota_limit) "
            "VALUES (?, ?, ?, ?, ?)",
            ("acc-1", 0, today, 100, 1000),
        )

        with pytest.raises(Exception):
            cursor.execute(
                "INSERT INTO account_quotas (account_id, key_id, quota_date, quota_remaining, quota_limit) "
                "VALUES (?, ?, ?, ?, ?)",
                ("acc-1", 0, today, 90, 1000),
            )


def test_account_quotas_distinct_per_key(database):
    """Different key_id values under the same (account_id, quota_date) are allowed."""
    with database.get_connection() as conn:
        cursor = conn.cursor()
        today = database.get_today_date()
        cursor.execute(
            "INSERT INTO account_quotas (account_id, key_id, quota_date, quota_remaining, quota_limit) "
            "VALUES (?, ?, ?, ?, ?)",
            ("acc-1", 0, today, 100, 1000),
        )
        cursor.execute(
            "INSERT INTO account_quotas (account_id, key_id, quota_date, quota_remaining, quota_limit) "
            "VALUES (?, ?, ?, ?, ?)",
            ("acc-1", 1, today, 200, 1000),
        )
        rows = conn.execute(
            "SELECT quota_remaining FROM account_quotas WHERE account_id = ? AND quota_date = ?",
            ("acc-1", today),
        ).fetchall()
        assert {r["quota_remaining"] for r in rows} == {100, 200}


def test_connection_is_new_each_time(database):
    """Verify get_connection creates a fresh connection on each use."""
    with database.get_connection() as conn1:
        with database.get_connection() as conn2:
            # Different connection objects
            assert conn1 is not conn2


def test_connection_closes_on_error(database):
    """Verify connection is closed and rolled back on error."""
    try:
        with database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO account_quotas (account_id, quota_date, "
                "quota_remaining, quota_limit) VALUES (?, ?, ?, ?)",
                ("a", "b", 1, 1),
            )
            cursor.execute("DROP TABLE non_existent")
    except sqlite3.OperationalError:
        pass

    # Subsequent use still works -> connection closed cleanly
    with database.get_connection() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1


def test_model_scope_account_dataclass():
    """Test ModelScopeAccount dataclass initialization, equality, and defaults."""
    from provider.models.account import ModelScopeAccount

    acc1 = ModelScopeAccount(account_id="a1", api_key="k1", base_url="https://p1.com")
    acc2 = ModelScopeAccount(account_id="a1", api_key="k1", base_url="https://p1.com")
    acc3 = ModelScopeAccount(account_id="a2", api_key="k2", base_url="https://p2.com")

    assert acc1.account_id == "a1"
    assert acc1.api_key == "k1"
    assert acc1.base_url == "https://p1.com"
    assert acc1 == acc2
    assert acc1 != acc3
    assert "a1" in repr(acc1)

    # Verify default values and post_init behavior
    acc_default = ModelScopeAccount(account_id="ad", api_key="kd", base_url="u")
    assert acc_default.quota_limit == 0
    assert acc_default.quota_remaining == 0
    assert acc_default.last_reset_date == ""
    assert acc_default.unavailable_models == set()


def test_foreign_keys_enabled(database):
    """Verify PRAGMA foreign_keys is ON within a connection."""
    with database.get_connection() as conn:
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1


def test_database_wal_mode_enabled(database):
    """Verify WAL journal mode is enabled for better concurrent performance."""
    with database.get_connection() as conn:
        cursor = conn.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.upper() == "WAL", f"Expected WAL, got {journal_mode}"


def test_database_synchronous_normal(database):
    """Verify synchronous is set to NORMAL for balanced performance."""
    with database.get_connection() as conn:
        cursor = conn.execute("PRAGMA synchronous")
        sync_mode = cursor.fetchone()[0]
        assert sync_mode == 1, f"Expected synchronous=NORMAL (1), got {sync_mode}"
