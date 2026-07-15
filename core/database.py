import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage SQLite database for quota and alias caching."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Create database connection."""
        self.conn = sqlite3.connect(self.db_url, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connection."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_tables(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Account quotas table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_quotas (
                    account_id TEXT PRIMARY KEY,
                    quota_date TEXT NOT NULL,
                    quota_remaining INTEGER,
                    quota_limit INTEGER,
                    unavailable_models TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(account_id, quota_date)
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

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_quota_date
                ON account_quotas(quota_date)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alias_cache
                ON model_alias_cache(alias_name, cache_date)
            """)

            logger.info("Database tables initialized")

    def get_today_date(self) -> str:
        """Get current date in YYYY-MM-DD format."""
        return datetime.now().strftime("%Y-%m-%d")

    def close(self):
        """Close database connection."""
        self.disconnect()
