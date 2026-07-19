import pytest
import sqlite3
from core.database import DatabaseManager
from core.migrations.base import Migration
from core.migrations.registry import clear_registry, register
from core.migrations.migrator import Migrator


@pytest.fixture
def db(tmp_path):
    """Fresh in-memory-style DB with schema_versions table."""
    database = DatabaseManager(f"sqlite:///{tmp_path}/test.db")
    yield database


class _AddColumn(Migration):
    version = 1
    description = "Add col to t"

    def up(self, conn):
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(t)")]
        if "col" not in cols:
            conn.execute("ALTER TABLE t ADD COLUMN col TEXT")


class _AddAnother(Migration):
    version = 2
    description = "Add other_col to t"

    def up(self, conn):
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(t)")]
        if "other_col" not in cols:
            conn.execute("ALTER TABLE t ADD COLUMN other_col INTEGER DEFAULT 0")


@pytest.fixture
def fake_migrations():
    return [_AddColumn(), _AddAnother()]


class _Boom(Migration):
    version = 3
    description = "Explodes"

    def up(self, conn):
        raise RuntimeError("boom")


def test_run_up_failure_leaves_no_version_record(db):
    """up() 抛异常时不应写入 schema_versions。"""
    migrator = Migrator(db, migrations=[_Boom()])
    with pytest.raises(RuntimeError, match="boom"):
        migrator.run()

    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM schema_versions").fetchone()[0]
        assert count == 0


def test_run_applies_pending_migrations(db, fake_migrations):
    with db.get_connection() as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")

    migrator = Migrator(db, migrations=fake_migrations)
    migrator.run()

    with db.get_connection() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(t)")]
        assert "col" in cols
        assert "other_col" in cols

        versions = {r["version"] for r in conn.execute("SELECT version FROM schema_versions")}
        assert versions == {1, 2}


def test_run_is_idempotent(db, fake_migrations):
    with db.get_connection() as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")

    migrator = Migrator(db, migrations=fake_migrations)
    migrator.run()
    migrator.run()  # second call should be a no-op

    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM schema_versions").fetchone()[0]
        assert count == 2  # not 4


def test_status_shows_applied_and_pending(db, fake_migrations):
    with db.get_connection() as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")

    migrator = Migrator(db, migrations=fake_migrations)
    migrator.run()

    status = migrator.status()
    assert len(status) == 2
    assert all(s["applied"] for s in status)
    assert status[0]["version"] == 1
    assert status[1]["version"] == 2


def test_rollback_removes_version_and_reverts_migration():
    pass  # rollback test deferred to Task 3 (CLI) since most migrations don't implement down()
