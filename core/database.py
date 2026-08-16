import datetime
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from typing import Generator, Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage SQLite database for quota, alias caching, accounts, and admin."""

    def __init__(self, db_url: str):
        # Strip sqlite:/// prefix for sqlite3.connect
        db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else db_url

        # If the parent directory doesn't exist (e.g. Windows path on WSL),
        # fall back to a database file in the project root.
        parent = Path(db_path).parent
        if not parent.exists():
            fallback = Path(__file__).resolve().parent.parent / "modelscope_proxy.db"
            logger.warning(
                f"Database path '{db_path}' is not accessible (parent dir '{parent}' does not exist). "
                f"Falling back to '{fallback}'"
            )
            db_path = str(fallback)

        # Ensure the parent directory exists for the fallback path too
        parent = Path(db_path).parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

        self.db_url = db_path

        # Bounded connection pool: reuse a handful of sqlite3 connections
        # instead of opening a brand-new one per query (which is expensive and
        # caps throughput under load). Connections are checked out exclusively
        # for the duration of a `with` block, so sharing across threads is safe.
        self._conn_pool: "Queue[sqlite3.Connection]" = Queue(maxsize=10)
        self._pool_max = 10

        # Decide journal mode once up-front via a real write probe (see
        # _probe_journal_mode). Trusting the reported PRAGMA result alone is
        # not enough on WSL /mnt/ DrvFs mounts, so this runs a real write.
        self._journal_mode = self._probe_journal_mode()

    def _new_connection(self) -> sqlite3.Connection:
        """Open a new sqlite3 connection with the project's PRAGMAs applied."""
        conn = sqlite3.connect(self.db_url, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Wait up to 5s for a lock instead of failing immediately. Removes the
        # "database is locked" OperationalError when the request path opens a
        # short-lived child connection while the outer transaction is in flight
        # (e.g. SELECT inside a write block, or nested repository calls).
        conn.execute("PRAGMA busy_timeout = 5000")

        # ── Write PRAGMAs (best-effort, WAL probed up-front) ────────────────
        # All three PRAGMAs below modify the database header. In WSL's /mnt/d/
        # mount, any write to the SQLite file can fail with
        # "unable to open database file" (fs translation layer issue).
        # Also, WAL may report success but fail to create .db-wal/.db-shm,
        # making subsequent writes fail — so the journal mode was already
        # verified with a real write probe in __init__, and every write here
        # falls back to SQLite defaults silently.

        if self._journal_mode == "wal":
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                logger.warning("WAL journal mode unavailable — using default journal mode")
            try:
                # synchronous=NORMAL (1) is safe with WAL and ~2x faster than FULL (2).
                conn.execute("PRAGMA synchronous = NORMAL")
            except sqlite3.OperationalError:
                logger.warning("synchronous=NORMAL unavailable — using default (FULL)")
        else:
            # File lives on a mount where WAL is unreliable (e.g. WSL DrvFs).
            # Make sure we're in DELETE mode, not a leftover half-WAL header.
            try:
                if conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal":
                    conn.execute("PRAGMA journal_mode = DELETE")
            except sqlite3.OperationalError:
                logger.warning("journal_mode query failed — leaving SQLite default")

        try:
            # Larger cache reduces disk I/O for the hot path (accounts, mappings).
            conn.execute("PRAGMA cache_size = -2000")  # 2MB page cache
        except sqlite3.OperationalError:
            logger.warning("custom cache_size unavailable — using SQLite default")
        return conn

    def _probe_journal_mode(self) -> str:
        """Return 'wal' if this DB file can *really* use WAL, else 'delete'.

        On WSL's /mnt/ DrvFs mounts, ``PRAGMA journal_mode=WAL`` can report
        success while failing to create its .db-wal/.db-shm sidecar files —
        leaving the file in a half-WAL state where every subsequent write
        raises "unable to open database file". So instead of trusting the
        reported mode, we verify with a real write. If the probe fails, we
        convert the file back to DELETE mode so the app stays usable.
        """
        logger.info(f"Probing journal mode for {self.db_url}")
        try:
            conn = sqlite3.connect(self.db_url, check_same_thread=False, timeout=10)
            try:
                conn.execute("PRAGMA busy_timeout = 10000")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                # Real write probe — reading the reported mode isn't enough.
                conn.execute("CREATE TABLE IF NOT EXISTS __journal_probe (x)")
                conn.execute("INSERT INTO __journal_probe VALUES (1)")
                conn.commit()
                conn.execute("DROP TABLE __journal_probe")
                conn.commit()
                return "wal"
            except sqlite3.OperationalError:
                # Don't leave the file half-WAL: force it back to DELETE mode.
                try:
                    conn.execute("PRAGMA journal_mode = DELETE")
                    conn.commit()
                except sqlite3.OperationalError:
                    logger.warning("could not restore journal mode to DELETE")
                return "delete"
            finally:
                conn.close()
        except sqlite3.OperationalError:
            logger.warning("journal-mode probe failed — using DELETE")
            return "delete"

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections (pooled).

        Reuses connections from a small pool instead of opening a new sqlite3
        connection on every query. Each connection is exclusive to one caller
        for the duration of the ``with`` block, so it is safe to share across
        threads (``check_same_thread=False`` + serial use).
        """
        try:
            conn = self._conn_pool.get_nowait()
        except Exception:
            conn = self._new_connection()
        # Re-enforce foreign-key enforcement on every checkout. Migrations may
        # temporarily disable FK (PRAGMA foreign_keys=OFF) to rebuild a parent
        # table without triggering ON DELETE CASCADE; this guarantees normal
        # queries always run with FK on, regardless of pooled-connection state.
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            # Return the connection to the bounded pool, or close it if full.
            if self._conn_pool.qsize() < self._pool_max:
                self._conn_pool.put(conn)
            else:
                conn.close()

    def close(self) -> None:
        """Close every pooled connection.

        Releases the open file handles held by the bounded pool. On Windows a
        SQLite database file cannot be deleted while any connection is open, so
        this must be called before cleanup removes the file (e.g. the test
        fixture teardown). Safe to call multiple times / when the pool is empty.
        """
        while True:
            try:
                conn = self._conn_pool.get_nowait()
            except Exception:
                break
            try:
                conn.close()
            except Exception:
                pass

    def vacuum(self):
        """Reclaim disk space by rebuilding the database file.

        SQLite ``DELETE`` only marks pages as free — the .db file never
        shrinks on its own. Call this after bulk deletions (e.g. log
        cleanup) to actually return the space to the OS.

        ``VACUUM`` cannot run inside a transaction, so a dedicated
        autocommit connection (``isolation_level=None``) is used instead of
        ``get_connection()`` (which wraps everything in a transaction).
        A WAL checkpoint (TRUNCATE) afterwards also shrinks the -wal file.
        """
        conn = sqlite3.connect(
            self.db_url, check_same_thread=False, isolation_level=None
        )
        try:
            # Wait for concurrent writers instead of failing immediately.
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.execute("VACUUM")
            # WAL checkpoint only valid when WAL mode is active.
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            if mode == "wal":
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logger.info("Database VACUUM completed — free pages reclaimed")
        finally:
            conn.close()

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
                    key_id INTEGER NOT NULL DEFAULT 0,
                    quota_remaining INTEGER NOT NULL DEFAULT 0,
                    quota_limit INTEGER NOT NULL DEFAULT 0,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    unavailable_models TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, key_id, quota_date)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_quotas (
                    account_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    key_id INTEGER NOT NULL DEFAULT 0,
                    quota_date TEXT NOT NULL,
                    quota_remaining INTEGER NOT NULL DEFAULT 0,
                    quota_limit INTEGER NOT NULL DEFAULT 0,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, model_name, key_id, quota_date)
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
                    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
                )
            """)

            # ── Admin tables ──

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    base_url TEXT NOT NULL,
                    provider_type TEXT NOT NULL DEFAULT 'modelscope',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    api_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    alias TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(account_id, api_key)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_rate_windows (
                    account_id TEXT NOT NULL,
                    model_name TEXT NOT NULL DEFAULT '__global__',
                    key_id INTEGER NOT NULL DEFAULT 0,
                    window_start TEXT NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, model_name, key_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS provider_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type_key TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    strategy_type TEXT NOT NULL DEFAULT 'header_based',
                    config TEXT NOT NULL DEFAULT '{}',
                    color TEXT NOT NULL DEFAULT '#89b4fa',
                    built_in INTEGER NOT NULL DEFAULT 0,
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
                    supplier_model_id INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (alias_name) REFERENCES model_mappings(alias_name) ON DELETE CASCADE,
                    FOREIGN KEY (supplier_model_id) REFERENCES supplier_models(id) ON DELETE CASCADE,
                    UNIQUE(alias_name, supplier_model_id)
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
                    client_key_name TEXT,
                    api_key_id INTEGER DEFAULT 0,
                    error_source TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_stats_minute (
                    bucket TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    account_id TEXT NOT NULL DEFAULT '',
                    client_key_name TEXT NOT NULL DEFAULT '',
                    requests INTEGER NOT NULL DEFAULT 0,
                    success INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    latency_sum INTEGER NOT NULL DEFAULT 0,
                    latency_count INTEGER NOT NULL DEFAULT 0,
                    cached_tokens INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (bucket, model, account_id, client_key_name)
                )
            """)
            # Migration: add virtual_model column to existing tables
            try:
                cursor.execute("ALTER TABLE request_stats_minute ADD COLUMN virtual_model TEXT NOT NULL DEFAULT ''")
            except Exception:
                pass  # Column already exists

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
                CREATE INDEX IF NOT EXISTS idx_logs_api_key
                ON request_logs(api_key_id)
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
                CREATE INDEX IF NOT EXISTS idx_mapping_models_supplier_model_id
                ON mapping_models(supplier_model_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_logs_alias
                ON operation_logs(alias_name, id DESC)
            """)

            # Unique index on accounts.name (paired with the baseline `name` column).
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_name
                ON accounts(name)
            """)

            logger.info("Database tables initialized")

    def seed_default_config(self):
        """Insert default system config values if not present."""
        defaults = [
            ("log_level", "INFO", "日志级别: DEBUG/INFO/WARNING/ERROR"),
            ("load_balancer_strategy", "round_robin", "负载均衡策略: round_robin/least_conn/random"),
            ("request_timeout_ms", "3600000", "读取超时(ReadTimeout)毫秒数：等待上游开始响应的最长时限"),
            ("auto_disable_on_quota", "true", "配额耗尽时自动禁用供应商"),
            ("auto_reset_daily", "true", "每日自动重置配额"),
            ("log_retention_hours", "1", "保留日志的小时数，超出则定时清理"),
        ]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            existing = {
                row[0] for row in cursor.execute("SELECT key FROM system_config")
            }
            for key, value, desc in defaults:
                if key not in existing:
                    cursor.execute(
                        "INSERT INTO system_config (key, value, description) VALUES (?, ?, ?)",
                        (key, value, desc),
                    )
            # One-time upgrade: the legacy default read timeout was 30000 ms (30s),
            # which is too short for upstream model generation. Bump any row still
            # carrying that legacy default to 1 hour (3600000 ms).
            cursor.execute(
                "UPDATE system_config SET value = ? WHERE key = ? AND value = ?",
                ("3600000", "request_timeout_ms", "30000"),
            )
            logger.info(f"Seeded {len(defaults) - len(existing)} default config values")

    def get_today_date(self) -> str:
        """Get current date in YYYY-MM-DD format (Asia/Shanghai)."""
        from core.timezone import today
        return today()
