# DB Migration Strategy Design

**Date**: 2026-07-19
**Status**: Approved
**Author**: Brainstorming session

## Problem Statement

`DatabaseManager.initialize_tables()` currently mixes `CREATE TABLE IF NOT EXISTS` with ~15 `ALTER TABLE` migration statements, all relying on `try/except OperationalError` to detect whether a change has already been applied. This approach has several problems:

1. **No version tracking** — there's no reliable way to know which migrations have been applied.
2. **Fragile detection** — catching `OperationalError` is a side-effect-based check, not an explicit state query.
3. **Monolithic method** — `initialize_tables()` is 460+ lines and growing; every schema change requires editing this single method.
4. **Hard to test** — you can't test a single migration in isolation; you can only test the whole `initialize_tables()` flow.
5. **No rollback path** — once a migration runs, there's no defined way to revert it.

The goal is a migration system that:
- Checks at startup whether each migration has been applied, and runs it if not.
- Keeps all DB schema changes in versioned migration classes, not scattered in application code.
- Supports all SQLite schema change types: add/remove columns, create/drop tables, index changes, and complex reconstructions (DROP COLUMN, UNIQUE constraint changes).

## Approach Comparison

| Approach | Pros | Cons |
|----------|------|------|
| **A: Lightweight custom framework** (chosen) | Zero new dependencies, full control, Python class handles complex SQLite ops, small codebase (~200 lines) | Self-maintained (small cost) |
| **B: Alembic** | Industry standard, auto-generates migrations | Requires SQLAlchemy ORM/Engine — overkill for a pure SQLite project without ORM |
| **C: Pure SQL scripts** | Lightest weight | Cannot handle SQLite's limitations (DROP COLUMN, constraint changes need table rebuild) |

**Chosen: Approach A** — custom lightweight migration framework.

## Architecture

### Startup Flow

```
ServiceInitializer.initialize_all()
  └─ DatabaseManager.initialize_tables()     ← CREATE TABLE IF NOT EXISTS + indexes only (no ALTERs)
  └─ Migrator(database).run()                ← check schema_versions, run pending up() in order
  └─ database.seed_default_config()
```

### Module Structure

```
core/
├── database.py              ← simplified: CREATE TABLE + indexes only, no ALTER migrations
└── migrations/
    ├── __init__.py          # exports Migration, Migrator
    ├── base.py              # Migration abstract base class
    ├── migrator.py          # Migrator: run() / rollback() / status()
    ├── cli.py               # python -m core.migrate [run|status|rollback N]
    └── migrations/          # numbered migration classes
        ├── __init__.py
        ├── 001_initial_baseline.py
        ├── 002_add_name_to_accounts.py
        └── ...
```

### Migration Base Class

```python
class Migration:
    """Abstract base for all schema migrations."""
    version: int            # strictly increasing version number
    description: str        # human-readable description

    def up(self, conn: sqlite3.Connection) -> None:
        """Apply the migration. Must be idempotent."""
        raise NotImplementedError

    def down(self, conn: sqlite3.Connection) -> None:
        """Revert the migration (for rollback)."""
        raise NotImplementedError
```

Each migration's `up()` includes an **idempotency check** (e.g., `PRAGMA table_info` to verify a column doesn't exist before `ALTER TABLE ADD COLUMN`). This ensures migrations work correctly whether the database is fresh or old.

### Migrator

```python
class Migrator:
    def __init__(self, database: DatabaseManager):
        self.db = database

    def run(self):
        """Execute all pending migrations in version order."""
        applied = self._get_applied_versions()
        pending = [m for m in get_all_migrations() if m.version not in applied]
        for migration in pending:
            with self.db.get_connection() as conn:
                migration.up(conn)
                conn.execute(
                    "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
                    (migration.version, migration.description),
                )
            logger.info(f"Migration {migration.version} applied: {migration.description}")

    def status(self) -> list[dict]:
        """List all migrations and their applied status."""
        ...

    def rollback(self, target: int):
        """Rollback to target version by calling down() in reverse order."""
        ...
```

### schema_versions Table

```sql
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Historical Migration Conversion

### Classification

| Original Logic | Destination |
|----------------|-------------|
| `CREATE TABLE IF NOT EXISTS` | Keep in `initialize_tables()` (baseline for fresh installs) |
| Simple `ADD COLUMN` migrations | Split into independent migration classes with idempotent `up()` |
| Complex migrations (DROP COLUMN, UNIQUE constraint changes, table rebuilds) | Split into independent migration classes with full Python logic in `up()` |

### Version Numbering

The current `CREATE TABLE` definitions (which already include all migrated columns) serve as the implicit baseline (version 0). All ALTER migrations start from version 1.

For fresh installs: `CREATE TABLE` creates tables with all columns → migration idempotency check finds column already exists → skips execution but still records version number (fast, one PRAGMA query per migration).

For old installs: `CREATE TABLE IF NOT EXISTS` succeeds (table exists, no schema change) → migration idempotency check finds column missing → applies ALTER.

### Complex Migration Example (DROP COLUMN)

```python
class Migration_007_DropRegionFromAccounts(Migration):
    version = 7
    description = "Drop region column from accounts"

    def up(self, conn):
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)")]
        if "region" not in cols:
            return  # already removed
        # SQLite < 3.35.0 doesn't support DROP COLUMN → rebuild table
        conn.execute("""CREATE TABLE accounts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL UNIQUE,
            ...
        )""")
        conn.execute("""INSERT INTO accounts_new (...)
            SELECT (... all columns except region) FROM accounts""")
        conn.execute("DROP TABLE accounts")
        conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
```

### Resulting initialize_tables()

After migration extraction, `initialize_tables()` shrinks to pure `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` statements, with no ALTER migration logic.

## Error Handling

- **Migration execution failure**: `get_connection()` context manager auto-rolls-back → `initialize_all()` raises → service fails to start. This is intentional: inconsistent schema is worse than failed startup.
- **Version number conflict/duplicate**: `schema_versions.version` is PRIMARY KEY → duplicate execution raises IntegrityError → Migrator catches and aborts.
- **Process killed mid-migration**: Since version record and DDL are in the same transaction (SQLite ALTER TABLE is transactional), uncommitted transactions auto-roll-back on next startup → migration re-runs safely (idempotency guarantees correctness).

## Testing Strategy

1. **Per-migration unit tests**:
   - Construct old schema (manually insert data to simulate old database state)
   - Execute `migration.up(conn)`
   - Assert schema change took effect (new column exists, old column gone, data correctly migrated)

2. **Migrator integration tests**:
   - Fresh install: `Migrator.run()` → all migrations marked as applied
   - Old database upgrade: start from empty DB, run migrations step by step, verify final schema is complete

3. **Test fixture adjustment**:
   - `conftest.py` `database` fixture calls `initialize_tables()` + `Migrator(database).run()`, matching production path

4. **Rollback tests**: Optional, only on critical migrations

## CLI Tool

```
python -m core.migrations.cli            # run pending migrations (same as startup)
python -m core.migrations.cli status     # show all migrations and applied status
python -m core.migrations.cli rollback N # rollback to version N
```

> **Rollback caveat**: `down()` for complex migrations (e.g., DROP COLUMN with table rebuild) **cannot recover deleted column data**. Rolling back such migrations restores the column structure but the data is lost. Treat rollback as a schema repair tool, not a data recovery mechanism.

## Scope

This migration system covers:
- Add/remove columns, change column types
- Create/drop tables
- Index changes (CREATE INDEX / DROP INDEX)
- Complex reconstructions (DROP COLUMN, UNIQUE constraint changes, table rebuilds)

## Out of Scope

- Data migrations (seeding, backfilling) — handled separately by `seed_default_config()` and similar mechanisms
- Cross-database support (MySQL/PostgreSQL) — SQLite only for now
- Migration autogeneration from model diffs
