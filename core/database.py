import datetime
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
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

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connection - creates new connection each time."""
        conn = sqlite3.connect(self.db_url, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_tables(self):
        """Initialize all database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # ── Existing tables ──

            # Account quotas table - composite primary key
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_quotas (
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

            # Alias cache table
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

            # ── New tables for admin panel ──

            # Accounts table - account configuration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL UNIQUE,
                    api_key TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Model mappings table - alias to actual model id
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL UNIQUE,
                    actual_model_id TEXT NOT NULL
                )
            """)

            # Supplier models table - models available on each supplier
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

            # System config table - key-value storage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Request logs table
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
                    raw_response TEXT
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

            # ── Migration: add `name` column to accounts if missing ──
            try:
                cursor.execute(
                    "ALTER TABLE accounts ADD COLUMN name TEXT NOT NULL DEFAULT ''"
                )
                cursor.execute(
                    "UPDATE accounts SET name = account_id WHERE name = ''"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Enforce name uniqueness (safe if already present)
            try:
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name)"
                )
            except (sqlite3.OperationalError, sqlite3.IntegrityError):
                pass  # Index already exists or conflicting data

            # ── Migration: add `account_name` column to request_logs if missing ──
            try:
                cursor.execute(
                    "ALTER TABLE request_logs ADD COLUMN account_name TEXT"
                )
                # Backfill: join with accounts to populate names
                cursor.execute(
                    """UPDATE request_logs SET account_name =
                       (SELECT name FROM accounts WHERE accounts.account_id = request_logs.account_id)
                       WHERE account_name IS NULL"""
                )
                logger.info("Migration: added 'account_name' column to request_logs table")
            except sqlite3.OperationalError:
                pass

            # ── Migration: drop `region` column from accounts (no longer needed) ──
            try:
                cursor.execute("ALTER TABLE accounts DROP COLUMN region")
                logger.info("Migration: dropped 'region' column from accounts table")
            except sqlite3.OperationalError:
                pass  # Column already dropped or doesn't exist

            # ── Migration: drop `region` column from model_mappings and fix UNIQUE constraint ──
            # Check if model_mappings has a 'region' column (legacy schema)
            try:
                cursor.execute(
                    "SELECT name FROM pragma_table_info('model_mappings') WHERE name = 'region'"
                )
                if cursor.fetchone():
                    # Legacy schema: recreate table without region and with UNIQUE(alias_name).
                    # Duplicates (same alias_name, different region) are collapsed by keeping
                    # the first row per alias_name (MIN(id)).
                    cursor.execute(
                        """CREATE TABLE model_mappings_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            alias_name TEXT NOT NULL UNIQUE,
                            actual_model_id TEXT NOT NULL
                        )"""
                    )
                    cursor.execute(
                        """INSERT INTO model_mappings_new (alias_name, actual_model_id)
                           SELECT alias_name, actual_model_id
                           FROM model_mappings
                           WHERE id IN (SELECT MIN(id) FROM model_mappings GROUP BY alias_name)"""
                    )
                    cursor.execute("DROP TABLE model_mappings")
                    cursor.execute("ALTER TABLE model_mappings_new RENAME TO model_mappings")
                    logger.info("Migration: recreated model_mappings without region column")
            except sqlite3.OperationalError:
                pass  # Table doesn't exist yet (will be created by CREATE TABLE IF NOT EXISTS above)

            logger.info("Database tables initialized")

    def seed_default_config(self):
        """Insert default system config values if not present."""
        defaults = [
            ("log_level", "INFO", "日志级别: DEBUG/INFO/WARNING/ERROR"),
            ("load_balancer_strategy", "round_robin", "负载均衡策略: round_robin/least_conn/random"),
            ("request_timeout_ms", "30000", "请求超时毫秒数"),
            ("retry_count", "0", "失败重试次数"),
            ("auto_disable_on_quota", "true", "配额耗尽时自动禁用供应商"),
            ("auto_reset_daily", "true", "每日自动重置配额"),
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
            logger.info(f"Seeded {len(defaults) - len(existing)} default config values")

    def get_today_date(self) -> str:
        """Get current date in YYYY-MM-DD format."""
        return datetime.datetime.now().strftime("%Y-%m-%d")
