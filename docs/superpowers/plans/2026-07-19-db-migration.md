# DB Migration Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ad-hoc ALTER TABLE migrations in `DatabaseManager.initialize_tables()` with a versioned migration system that checks at startup and applies un-run migrations.

**Architecture:** A lightweight migration framework under `core/migrations/`. Each schema change is a numbered `Migration` subclass with idempotent `up()` / `down()` methods. `Migrator.run()` queries a `schema_versions` table, executes pending migrations in order, and records each applied version. Wired into `ServiceInitializer.initialize_all()` via a single synchronous call after `initialize_tables()`.

**Tech Stack:** Python stdlib (`sqlite3`, `abc`, `argparse`, `logging`, `pathlib`) + project's existing `DatabaseManager`. Zero new dependencies.

## Global Constraints
- No new pip dependencies — use only stdlib.
- Each migration's `up()` must be idempotent (safe to call multiple times).
- `Migrator.run()` executes synchronously and blocks startup until all pending migrations complete.
- Startup must fail loudly if any migration fails (schema inconsistency is worse than no startup).
- Tests must exercise the full migration path (no bypassing `Migrator` in fixtures).
- Follow the project's existing import pattern: `from core.xxx import` with `provider.*` fallback in `main.py` only.
- Match existing code style: docstrings, logging via `logger = logging.getLogger(__name__)`, `snake_case` file names.

---

## File Structure

```
core/
├── database.py                          # MODIFY — remove all ALTER migration logic, keep CREATE TABLE + indexes
└── migrations/
    ├── __init__.py                      # CREATE — exports Migration, Migrator, get_all_migrations, register
    ├── base.py                          # CREATE — Migration abstract base class
    ├── migrator.py                      # CREATE — Migrator: run(), status(), rollback()
    ├── registry.py                      # CREATE — @register decorator + get_all_migrations()
    ├── cli.py                           # CREATE — python -m core.migrations.cli
    └── migrations/
        ├── __init__.py                  # CREATE — auto-imports all migration modules
        ├── 001_account_quotas_tokens.py # CREATE — add total_input/output_tokens
        ├── 002_request_logs_response_headers.py
        ├── 003_accounts_name.py
        ├── 004_request_logs_account_name.py
        ├── 005_accounts_drop_region.py
        ├── 006_request_logs_timing.py
        ├── 007_model_mappings_rebuild.py
        ├── 008_request_logs_client_key_name.py
        ├── 009_model_mappings_metadata.py
        └── 010_mapping_models_sort_order.py

tests/
├── conftest.py                          # MODIFY — database fixture also runs Migrator
└── core/
    └── migrations/
        ├── __init__.py
        ├── test_migrator.py             # CREATE — Migrator unit tests
        └── test_migrations.py           # CREATE — per-migration idempotency + upgrade tests
```

---

## Task 1: Migration base class + registry

**Files:**
- Create: `core/migrations/__init__.py`
- Create: `core/migrations/base.py`
- Create: `core/migrations/registry.py`

**Interfaces:**
- Produces: `Migration` (ABC with `version: int`, `description: str`, `up(conn)`, `down(conn)`)
- Produces: `register(cls)` decorator that adds migration class to registry
- Produces: `get_all_migrations()` → sorted list of migration instances

- [ ] **Step 1: Write the failing test**

Create `tests/core/migrations/__init__.py` (empty).

Create `tests/core/migrations/test_registry.py`:
```python
import pytest
from core.migrations.base import Migration
from core.migrations.registry import register, get_all_migrations, clear_registry


def test_register_and_get_all_migrations():
    clear_registry()

    @register
    class FakeMigration(Migration):
        version = 1
        description = "fake"

        def up(self, conn):
            pass

    migrations = get_all_migrations()
    assert len(migrations) == 1
    assert migrations[0].version == 1
    assert migrations[0].description == "fake"


def test_get_all_migrations_sorted_by_version():
    clear_registry()

    @register
    class M2(Migration):
        version = 2
        description = "second"

        def up(self, conn):
            pass

    @register
    class M1(Migration):
        version = 1
        description = "first"

        def up(self, conn):
            pass

    migrations = get_all_migrations()
    assert [m.version for m in migrations] == [1, 2]


def test_migration_base_is_abc():
    with pytest.raises(TypeError):
        Migration()  # abstract class
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_registry.py -v`
Expected: FAIL — `core.migrations` module doesn't exist

- [ ] **Step 3: Create `core/migrations/base.py`**

```python
"""Migration abstract base class."""

from abc import ABC, abstractmethod
import sqlite3


class Migration(ABC):
    """Abstract base for all schema migrations.

    Subclasses define ``version`` (unique, increasing int),
    ``description`` (human-readable), and implement ``up()``.
    ``down()`` is optional — raise NotImplementedError if unsupported.
    """

    version: int
    description: str

    @abstractmethod
    def up(self, conn: sqlite3.Connection) -> None:
        """Apply the migration. Must be idempotent."""
        ...

    def down(self, conn: sqlite3.Connection) -> None:
        """Revert the migration. Override in subclass if rollback is supported."""
        raise NotImplementedError(
            f"Migration {self.version} ({self.description}) does not support down()"
        )
```

- [ ] **Step 4: Create `core/migrations/registry.py`**

```python
"""Migration registry — collects all registered migration classes."""

from core.migrations.base import Migration

_ALL_MIGRATIONS: list[type[Migration]] = []


def register(cls: type[Migration]) -> type[Migration]:
    """Class decorator: register a migration class in the global registry."""
    _ALL_MIGRATIONS.append(cls)
    return cls


def get_all_migrations() -> list[Migration]:
    """Instantiate and return all registered migrations sorted by version."""
    return sorted([cls() for cls in _ALL_MIGRATIONS], key=lambda m: m.version)


def clear_registry() -> None:
    """Reset registry (for testing only)."""
    _ALL_MIGRATIONS.clear()
```

- [ ] **Step 5: Create `core/migrations/__init__.py`**

```python
"""Lightweight schema migration framework."""

from core.migrations.base import Migration
from core.migrations.migrator import Migrator
from core.migrations.registry import get_all_migrations, register

__all__ = ["Migration", "Migrator", "get_all_migrations", "register"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_registry.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/migrations/base.py core/migrations/registry.py core/migrations/__init__.py tests/core/migrations/__init__.py tests/core/migrations/test_registry.py
git commit -m "feat(migrations): add Migration base class and registry"
```

---

## Task 2: Migrator

**Files:**
- Create: `core/migrations/migrator.py`
- Create: `tests/core/migrations/test_migrator.py`

**Interfaces:**
- Consumes: `DatabaseManager` (from `core.database`)
- Consumes: `get_all_migrations()` (from `core.migrations.registry`)
- Produces: `Migrator` class with `run()`, `status()`, `rollback(target_version)`

- [ ] **Step 1: Write the failing test**

Create `tests/core/migrations/test_migrator.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_migrator.py -v`
Expected: FAIL — `Migrator` not defined

- [ ] **Step 3: Create `core/migrations/migrator.py`**

```python
"""Migrator — executes pending migrations in version order."""

import logging
import sqlite3

from core.database import DatabaseManager
from core.migrations.registry import get_all_migrations

logger = logging.getLogger(__name__)

_VERSION_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS schema_versions (
        version INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


class Migrator:
    """Run, inspect, and rollback schema migrations."""

    def __init__(self, database: DatabaseManager, migrations: list | None = None):
        self.db = database
        self._migrations = migrations  # None → use global registry

    def _ensure_version_table(self) -> None:
        with self.db.get_connection() as conn:
            conn.execute(_VERSION_TABLE_SQL)

    def _get_applied_versions(self) -> set[int]:
        self._ensure_version_table()
        with self.db.get_connection() as conn:
            return {row["version"] for row in conn.execute("SELECT version FROM schema_versions")}

    def _get_migrations(self) -> list:
        return self._migrations if self._migrations is not None else get_all_migrations()

    def run(self) -> None:
        """Execute all pending migrations in version order."""
        applied = self._get_applied_versions()
        migrations = self._get_migrations()
        pending = [m for m in migrations if m.version not in applied]

        if not pending:
            logger.info("No pending migrations")
            return

        for m in pending:
            logger.info(f"Running migration {m.version}: {m.description}")
            with self.db.get_connection() as conn:
                m.up(conn)
                conn.execute(
                    "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
                    (m.version, m.description),
                )
            logger.info(f"Migration {m.version} applied")

    def status(self) -> list[dict]:
        """List all migrations with their applied status."""
        applied = self._get_applied_versions()
        migrations = self._get_migrations()
        return [
            {
                "version": m.version,
                "description": m.description,
                "applied": m.version in applied,
            }
            for m in migrations
        ]

    def rollback(self, target: int) -> None:
        """Rollback to target version, calling down() in reverse order."""
        applied = self._get_applied_versions()
        migrations = self._get_migrations()
        to_revert = [m for m in migrations if m.version > target and m.version in applied]

        if not to_revert:
            logger.info(f"Already at or below version {target}")
            return

        for m in reversed(to_revert):
            logger.info(f"Rolling back migration {m.version}: {m.description}")
            with self.db.get_connection() as conn:
                m.down(conn)
                conn.execute("DELETE FROM schema_versions WHERE version = ?", (m.version,))
            logger.info(f"Migration {m.version} rolled back")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_migrator.py -v`
Expected: PASS (the `test_rollback` stub passes trivially)

- [ ] **Step 5: Commit**

```bash
git add core/migrations/migrator.py tests/core/migrations/test_migrator.py
git commit -m "feat(migrations): add Migrator with run/status/rollback"
```

---

## Task 3: CLI module

**Files:**
- Create: `core/migrations/cli.py`

**Interfaces:**
- Consumes: `Migrator`, `DatabaseManager`, `ConfigManager`
- Produces: `python -m core.migrations.cli [run|status|rollback N]`

- [ ] **Step 1: Create `core/migrations/cli.py`**

```python
"""CLI entry point: python -m core.migrations.cli [run|status|rollback N]."""

import argparse
import logging
import sys

from core.config import ConfigManager
from core.database import DatabaseManager
from core.migrations.migrator import Migrator

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DB schema migration tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run all pending migrations")
    subparsers.add_parser("status", help="Show migration status")

    rollback_parser = subparsers.add_parser("rollback", help="Rollback to target version")
    rollback_parser.add_argument("target", type=int, help="Target version number")

    args = parser.parse_args(argv)

    config = ConfigManager()
    database = DatabaseManager(config.get_database_url())
    migrator = Migrator(database)

    if args.command == "run":
        migrator.run()
        return 0
    if args.command == "status":
        for entry in migrator.status():
            flag = "✓" if entry["applied"] else "✗"
            print(f"  {flag} {entry['version']:>3}: {entry['description']}")
        return 0
    if args.command == "rollback":
        migrator.rollback(args.target)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test the CLI**

Run: `cd D:/workspace/ai/modelscope-provider && python -m core.migrations.cli status`
Expected: Lists no migrations (empty registry) without error.

- [ ] **Step 3: Commit**

```bash
git add core/migrations/cli.py
git commit -m "feat(migrations): add CLI for run/status/rollback"
```

---

## Task 4: Migration auto-import module

**Files:**
- Create: `core/migrations/migrations/__init__.py`
- Create: `core/migrations/migrations/__init__.pyi` (optional, skip — not needed)

**Interfaces:**
- Produces: auto-import mechanism that triggers `@register` decorators on all migration modules
- Produces: `ALL_MIGRATIONS` list for potential direct access

- [ ] **Step 1: Create `core/migrations/migrations/__init__.py`**

```python
"""Auto-import all migration modules to trigger @register decorators."""

import importlib
from pathlib import Path

_module_base = __name__
_dir = Path(__file__).parent

for _file in sorted(_dir.glob("*.py")):
    if _file.stem != "__init__":
        importlib.import_module(f"{_module_base}.{_file.stem}")
```

- [ ] **Step 2: Verify auto-import works**

Run: `cd D:/workspace/ai/modelscope-provider && python -c "from core.migrations.registry import get_all_migrations; print(get_all_migrations())"`
Expected: `[]` (empty, because no migration files exist yet — but no import error).

- [ ] **Step 3: Commit**

```bash
git add core/migrations/migrations/__init__.py
git commit -m "feat(migrations): add auto-import mechanism for migration modules"
```

---

## Task 5: Simple ADD COLUMN migrations

**Files:**
- Create: `core/migrations/migrations/001_account_quotas_tokens.py`
- Create: `core/migrations/migrations/002_request_logs_response_headers.py`
- Create: `core/migrations/migrations/008_request_logs_client_key_name.py`
- Create: `tests/core/migrations/test_migrations.py` (will grow in later tasks)

**Interfaces:**
- Each migration file exports one `@register`-decorated Migration subclass
- All implement idempotent `up(conn)` with `PRAGMA table_info` guard
- `down(conn)` left as default (NotImplementedError)

- [ ] **Step 1: Create `core/migrations/migrations/001_account_quotas_tokens.py`**

```python
"""Migration 001: add total_input_tokens and total_output_tokens to account_quotas."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountQuotasTokens(Migration):
    version = 1
    description = "Add total_input_tokens and total_output_tokens to account_quotas"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(account_quotas)")]
        if "total_input_tokens" not in cols:
            conn.execute(
                "ALTER TABLE account_quotas ADD COLUMN total_input_tokens INTEGER NOT NULL DEFAULT 0"
            )
        if "total_output_tokens" not in cols:
            conn.execute(
                "ALTER TABLE account_quotas ADD COLUMN total_output_tokens INTEGER NOT NULL DEFAULT 0"
            )
```

- [ ] **Step 2: Create `core/migrations/migrations/002_request_logs_response_headers.py`**

```python
"""Migration 002: add response_headers to request_logs."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsResponseHeaders(Migration):
    version = 2
    description = "Add response_headers to request_logs"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        if "response_headers" not in cols:
            conn.execute("ALTER TABLE request_logs ADD COLUMN response_headers TEXT")
```

- [ ] **Step 3: Create `core/migrations/migrations/008_request_logs_client_key_name.py`**

```python
"""Migration 008: add client_key_name to request_logs."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsClientKeyName(Migration):
    version = 8
    description = "Add client_key_name to request_logs"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        if "client_key_name" not in cols:
            conn.execute("ALTER TABLE request_logs ADD COLUMN client_key_name TEXT")
```

- [ ] **Step 4: Write tests for these migrations**

Append to `tests/core/migrations/test_migrations.py` (create if not exists):
```python
"""Tests for individual migration classes."""

import sqlite3
import pytest
from core.database import DatabaseManager
from core.migrations.migrations import (
    AccountQuotasTokens,
    RequestLogsResponseHeaders,
    RequestLogsClientKeyName,
)


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
```

- [ ] **Step 5: Run tests**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_migrations.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add core/migrations/migrations/001_account_quotas_tokens.py core/migrations/migrations/002_request_logs_response_headers.py core/migrations/migrations/008_request_logs_client_key_name.py tests/core/migrations/test_migrations.py
git commit -m "feat(migrations): add ADD COLUMN migrations 001/002/008"
```

---

## Task 6: Migrations with backfill logic

**Files:**
- Create: `core/migrations/migrations/003_accounts_name.py`
- Create: `core/migrations/migrations/004_request_logs_account_name.py`
- Modify: `tests/core/migrations/test_migrations.py`

- [ ] **Step 1: Create `core/migrations/migrations/003_accounts_name.py`**

```python
"""Migration 003: add name column to accounts + create unique index."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountsName(Migration):
    version = 3
    description = "Add name column to accounts with unique index"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "name" not in cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN name TEXT NOT NULL DEFAULT ''")
            conn.execute("UPDATE accounts SET name = account_id WHERE name = ''")
        # Idempotent — CREATE UNIQUE INDEX IF NOT EXISTS is safe to re-run
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name)"
        )
```

- [ ] **Step 2: Create `core/migrations/migrations/004_request_logs_account_name.py`**

```python
"""Migration 004: add account_name to request_logs with backfill from accounts."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsAccountName(Migration):
    version = 4
    description = "Add account_name to request_logs with backfill"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        if "account_name" not in cols:
            conn.execute("ALTER TABLE request_logs ADD COLUMN account_name TEXT")
            conn.execute(
                """UPDATE request_logs SET account_name =
                   (SELECT name FROM accounts WHERE accounts.account_id = request_logs.account_id)
                   WHERE account_name IS NULL"""
            )
```

- [ ] **Step 3: Write tests**

Append to `tests/core/migrations/test_migrations.py`:
```python
from core.migrations.migrations import (
    AccountsName,
    RequestLogsAccountName,
    # previous imports...
)


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
```

- [ ] **Step 4: Run tests**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_migrations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/migrations/migrations/003_accounts_name.py core/migrations/migrations/004_request_logs_account_name.py tests/core/migrations/test_migrations.py
git commit -m "feat(migrations): add backfill migrations 003/004"
```

---

## Task 7: Complex migrations (DROP COLUMN, table rebuild, multi-column)

**Files:**
- Create: `core/migrations/migrations/005_accounts_drop_region.py`
- Create: `core/migrations/migrations/006_request_logs_timing.py`
- Create: `core/migrations/migrations/007_model_mappings_rebuild.py`
- Create: `core/migrations/migrations/009_model_mappings_metadata.py`
- Create: `core/migrations/migrations/010_mapping_models_sort_order.py`
- Modify: `tests/core/migrations/test_migrations.py`

- [ ] **Step 1: Create `core/migrations/migrations/005_accounts_drop_region.py`**

```python
"""Migration 005: drop region column from accounts (table rebuild)."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountsDropRegion(Migration):
    version = 5
    description = "Drop region column from accounts"

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "region" not in cols:
            return  # already removed

        # SQLite < 3.35 doesn't support DROP COLUMN → rebuild
        conn.execute("""
            CREATE TABLE accounts_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL UNIQUE,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                name TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO accounts_new (id, account_id, api_key, base_url, status, name, created_at, updated_at)
            SELECT id, account_id, api_key, base_url, status, name, created_at, updated_at
            FROM accounts
        """)
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
        # Preserve unique index on name
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name)"
        )
```

- [ ] **Step 2: Create `core/migrations/migrations/006_request_logs_timing.py`**

```python
"""Migration 006: add timing + cached token columns to request_logs."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class RequestLogsTiming(Migration):
    version = 6
    description = "Add timing and cached token columns to request_logs"

    _COLUMNS = {
        "request_start": "DATETIME",
        "first_response": "DATETIME",
        "end_time": "DATETIME",
        "cached_tokens": "INTEGER DEFAULT 0",
        "prompt_partial_cached": "INTEGER DEFAULT 0",
    }

    def up(self, conn: sqlite3.Connection) -> None:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(request_logs)")]
        for col_name, col_type in self._COLUMNS.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE request_logs ADD COLUMN {col_name} {col_type}")
```

- [ ] **Step 3: Create `core/migrations/migrations/007_model_mappings_rebuild.py`**

```python
"""Migration 007: drop region from model_mappings, enforce UNIQUE(alias_name)."""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class ModelMappingsRebuild(Migration):
    version = 7
    description = "Rebuild model_mappings: drop region, enforce UNIQUE(alias_name)"

    def up(self, conn: sqlite3.Connection) -> None:
        # Check if region column exists (legacy schema)
        try:
            conn.execute(
                "SELECT name FROM pragma_table_info('model_mappings') WHERE name = 'region'"
            )
            has_region = conn.fetchone() is not None
        except Exception:
            has_region = False

        if not has_region:
            # Still need to ensure UNIQUE(alias_name) is in place
            # Check current columns to see if we also need description/status columns
            # (those are handled by migration 009, so here we just fix UNIQUE)
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
```

- [ ] **Step 4: Create `core/migrations/migrations/009_model_mappings_metadata.py`**

```python
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
```

- [ ] **Step 5: Create `core/migrations/migrations/010_mapping_models_sort_order.py`**

```python
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
```

- [ ] **Step 6: Write tests**

Append to `tests/core/migrations/test_migrations.py` (add these imports at the top of the file):
```python
from core.migrations.migrations import (
    AccountsDropRegion,
    RequestLogsTiming,
    ModelMappingsRebuild,
    ModelMappingsMetadata,
    MappingModelsSortOrder,
)
```

Then append the test classes:
```python
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
            AccountsDropRegion().up(conn)

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
            RequestLogsTiming().up(conn)

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
            ModelMappingsRebuild().up(conn)

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
            ModelMappingsMetadata().up(conn)

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
            MappingModelsSortOrder().up(conn)

        with db.get_connection() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(mapping_models)")]
            assert "sort_order" in cols
```

- [ ] **Step 7: Run tests**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_migrations.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add core/migrations/migrations/005_accounts_drop_region.py core/migrations/migrations/006_request_logs_timing.py core/migrations/migrations/007_model_mappings_rebuild.py core/migrations/migrations/009_model_mappings_metadata.py core/migrations/migrations/010_mapping_models_sort_order.py tests/core/migrations/test_migrations.py
git commit -m "feat(migrations): add complex migrations 005/006/007/009/010"
```

---

## Task 8: Simplify `database.py`

**Files:**
- Modify: `core/database.py` (lines 58–437, the `initialize_tables` method)

**Interfaces:**
- `initialize_tables()` keeps only `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`
- All ALTER TABLE migration blocks are removed

- [ ] **Step 1: Rewrite `initialize_tables()` in `core/database.py`**

Replace the entire body of `initialize_tables()` (lines 58–437) with:

```python
    def initialize_tables(self):
        """Create all tables and indexes at the latest baseline schema.

        Schema migrations (ALTER TABLE) are handled separately by the
        ``core.migrations`` framework — see ``Migrator.run()``.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # ── Core tables ──

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_quotas (
                    account_id TEXT NOT NULL,
                    quota_date TEXT NOT NULL,
                    quota_remaining INTEGER NOT NULL DEFAULT 0,
                    quota_limit INTEGER NOT NULL DEFAULT 0,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    unavailable_models TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, quota_date)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_quotas (
                    account_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    quota_date TEXT NOT NULL,
                    quota_remaining INTEGER NOT NULL DEFAULT 0,
                    quota_limit INTEGER NOT NULL DEFAULT 0,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, model_name, quota_date)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_alias_cache (
                    account_id TEXT NOT NULL,
                    alias_name TEXT NOT NULL,
                    actual_model_id TEXT NOT NULL,
                    cache_date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, alias_name, cache_date),
                    FOREIGN KEY (account_id) REFERENCES account_quotas(account_id) ON DELETE CASCADE
                )
            """)

            # ── Admin tables ──

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    api_key TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL UNIQUE,
                    actual_model_id TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS supplier_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    model_name TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    context_length INTEGER,
                    UNIQUE(supplier_id, model_name)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mapping_models (
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    action_detail TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    model TEXT NOT NULL,
                    actual_model_id TEXT,
                    account_id TEXT,
                    account_name TEXT,
                    status_code INTEGER,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    latency_ms INTEGER,
                    is_stream BOOLEAN DEFAULT 0,
                    error_message TEXT,
                    raw_request TEXT,
                    raw_response TEXT,
                    response_headers TEXT,
                    cached_tokens INTEGER DEFAULT 0,
                    prompt_partial_cached INTEGER DEFAULT 0,
                    request_start TEXT,
                    first_response TEXT,
                    end_time TEXT,
                    client_key_name TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_value TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active',
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ── Indexes ──

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_quota_date
                ON account_quotas(quota_date)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alias_cache
                ON model_alias_cache(alias_name, cache_date)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_time
                ON request_logs(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_account
                ON request_logs(account_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_supplier_models_name
                ON supplier_models(model_name)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_supplier_models_supplier
                ON supplier_models(supplier_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mapping_models_alias
                ON mapping_models(alias_name)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mapping_models_supplier
                ON mapping_models(supplier_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_logs_alias
                ON operation_logs(alias_name, id DESC)
            """)

            logger.info("Database tables initialized")
```

Key changes:
1. Removed ALL `ALTER TABLE` migration blocks (lines 64–425 of original)
2. Added `name TEXT NOT NULL DEFAULT ''` to `accounts` CREATE TABLE (was added by migration 003 in old code; now part of baseline)
3. Added `description`, `status`, timestamps to `model_mappings` CREATE TABLE (were added by migration 009)
4. Kept all `CREATE TABLE IF NOT EXISTS` definitions matching the final schema
5. Kept all `CREATE INDEX IF NOT EXISTS` definitions

- [ ] **Step 2: Verify existing tests pass**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/test_database.py -v`
Expected: PASS (table structures unchanged from the test's perspective)

- [ ] **Step 3: Commit**

```bash
git add core/database.py
git commit -m "refactor(database): remove ALTER migrations, baseline now includes all columns"
```

---

## Task 9: Wire Migrator into ServiceInitializer + update conftest

**Files:**
- Modify: `core/service_init.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- `ServiceInitializer.initialize_all()` calls `Migrator(database).run()` after `initialize_tables()`
- Test `database` fixture also runs migrations

- [ ] **Step 1: Modify `core/service_init.py`**

Add import at top (matches existing `from core.xxx import` style in this file):
```python
from core.migrations import Migrator
```

In `initialize_all()` (after `database.initialize_tables()` and before `database.seed_default_config()`):
```python
        # Initialize database
        database = DatabaseManager(self.config.get_database_url())
        database.initialize_tables()

        # Run schema migrations (idempotent — skips already-applied migrations)
        Migrator(database).run()

        database.seed_default_config()
```

- [ ] **Step 2: Modify `tests/conftest.py`**

Add import at top (matches existing `from provider.core.xxx import` style in this file):
```python
from provider.core.migrations import Migrator
```

Update `database` fixture (after `db.initialize_tables()`):
```python
@pytest.fixture
def database(test_db_url):
    """Database manager fixture — uses isolated test DB, cleaned up after."""
    db = DatabaseManager(test_db_url)
    db.initialize_tables()
    Migrator(db).run()
    yield db
    db_path = Path(_test_db_path)
    if db_path.exists():
        db_path.unlink()
```

- [ ] **Step 3: Run full test suite**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add core/service_init.py tests/conftest.py
git commit -m "feat: wire Migrator into ServiceInitializer and test fixture"
```

---

## Task 10: Integration tests

**Files:**
- Create: `tests/core/migrations/test_integration.py`

**Interfaces:**
- Tests the full Migrator flow with all 10 migrations against a simulated old database
- Tests fresh-install path (Migrator runs on a DB created by initialize_tables())

- [ ] **Step 1: Write integration tests**

Create `tests/core/migrations/test_integration.py`:
```python
"""Integration tests: full migration flow end-to-end."""

import pytest
from pathlib import Path
from core.database import DatabaseManager
from core.migrations import Migrator, get_all_migrations
from core.migrations.registry import clear_registry


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
        assert len(status) == 10
        assert all(s["applied"] for s in status)

    def test_idempotent_on_fresh_install(self, db):
        db.initialize_tables()
        migrator = Migrator(db)
        migrator.run()
        migrator.run()  # second run no-op

        status = migrator.status()
        assert len(status) == 10
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
        assert len(status) == 10
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
    def test_ten_migrations_registered(self):
        migrations = get_all_migrations()
        assert len(migrations) == 10
        versions = [m.version for m in migrations]
        assert versions == list(range(1, 11))
```

- [ ] **Step 2: Run integration tests**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/core/migrations/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full suite**

Run: `cd D:/workspace/ai/modelscope-provider && python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/core/migrations/test_integration.py
git commit -m "test(migrations): add integration tests for full migration flow"
```

---

## Self-Review Notes

**Spec coverage checklist:**
- ✅ Migration base class + version tracking → Task 1, 2
- ✅ schema_versions table → Task 2 (Migrator._ensure_version_table)
- ✅ Idempotent up() with PRAGMA guard → Tasks 5–7 (all migration classes)
- ✅ Historical migration conversion → Tasks 5–7 (all 10 ALTER blocks converted)
- ✅ Simplified initialize_tables() → Task 8
- ✅ Wired into ServiceInitializer → Task 9
- ✅ CLI tool (run/status/rollback) → Task 3
- ✅ Test strategy (per-migration + integration) → Tasks 5–7, 10
- ✅ Error handling (transactional, fail-startup) → Task 2 (get_connection rollback)
- ✅ down() optional → Task 1 (base class raises NotImplementedError)

**Placeholder scan:** No TBD/TODO patterns found. All code blocks are complete.

**Type consistency:** `Migrator.__init__(self, database: DatabaseManager)` used consistently. `get_all_migrations()` returns `list[Migration]` throughout. Migration versions 1–10 sequential.
