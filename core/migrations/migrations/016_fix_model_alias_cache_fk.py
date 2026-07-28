import sqlite3

from core.migrations.base import Migration
from core.migrations.registry import register


@register
class FixModelAliasCacheFk(Migration):
    """Fix model_alias_cache FK to reference the unique ``accounts(account_id)``.

    The baseline schema declared
    ``FOREIGN KEY (account_id) REFERENCES account_quotas(account_id)``, but
    ``account_quotas.account_id`` is only part of a composite primary key (not
    unique). With ``foreign_keys=ON`` any future ``INSERT`` into
    ``model_alias_cache`` would raise "foreign key mismatch". Point the FK at
    ``accounts(account_id)`` instead (a UNIQUE column). The table is unused by
    the request path, so rebuilding it is safe.
    """

    version = 16
    description = "Fix model_alias_cache FK to reference unique accounts(account_id)"

    def up(self, conn: sqlite3.Connection) -> None:
        conn.execute("DROP TABLE IF EXISTS model_alias_cache")
        conn.execute(
            """
            CREATE TABLE model_alias_cache (
                account_id TEXT NOT NULL,
                alias_name TEXT NOT NULL,
                actual_model_id TEXT NOT NULL,
                cache_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, alias_name, cache_date),
                FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
            )
        """
        )
