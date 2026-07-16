import json
import logging
import os
from typing import List, Dict, Optional

from dotenv import load_dotenv
from provider.models.account import ModelScopeAccount

load_dotenv()

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage configuration from environment variables and/or database."""

    def __init__(self, db=None):
        """
        Args:
            db: Optional DatabaseManager instance. If provided, accounts
                will be loaded from the database first.
        """
        self.db = db

    @staticmethod
    def load_accounts_from_env() -> List[ModelScopeAccount]:
        """Load ModelScope accounts from environment variable."""
        accounts_json = os.getenv("MODELSCOPE_ACCOUNTS_JSON")

        if not accounts_json:
            raise ValueError("MODELSCOPE_ACCOUNTS_JSON environment variable is not set")

        try:
            accounts = json.loads(accounts_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse MODELSCOPE_ACCOUNTS_JSON: {e}")

        accounts_list = []
        for account_data in accounts:
            account = ModelScopeAccount(
                account_id=account_data["account_id"],
                api_key=account_data["api_key"],
                base_url=account_data["base_url"]
            )
            accounts_list.append(account)

        if not accounts_list:
            raise ValueError("No ModelScope accounts configured")

        return accounts_list

    def load_accounts_from_db(self) -> List[ModelScopeAccount]:
        """Load ModelScope accounts from database."""
        if not self.db:
            raise ValueError("Database not configured, cannot load accounts from DB")

        from provider.repositories.account_repository import AccountRepository
        repo = AccountRepository(self.db)
        db_accounts = repo.find_active()

        if not db_accounts:
            return []

        accounts = []
        for a in db_accounts:
            accounts.append(ModelScopeAccount(
                account_id=a["account_id"],
                api_key=a["api_key"],
                base_url=a["base_url"],
            ))
        return accounts

    def load_accounts(self, migrate_from_env: bool = True) -> List[ModelScopeAccount]:
        """Load accounts, preferring DB over .env.

        If migrate_from_env is True and DB is empty, auto-migrate from
        MODELSCOPE_ACCOUNTS_JSON to the database.
        """
        if not self.db:
            return self.load_accounts_from_env()

        # Try DB first
        accounts = self.load_accounts_from_db()

        if accounts:
            logger.info(f"Loaded {len(accounts)} accounts from database")
            return accounts

        # DB is empty - migrate from .env if requested
        if migrate_from_env:
            try:
                env_accounts = self.load_accounts_from_env()
                self._migrate_accounts_to_db(env_accounts)
                logger.info(f"Migrated {len(env_accounts)} accounts from .env to database")
                return env_accounts
            except ValueError as e:
                logger.error(f"Failed to load accounts: {e}")
                raise

        raise ValueError("No accounts found in database and migration disabled")

    def _migrate_accounts_to_db(self, accounts: List[ModelScopeAccount]):
        """Migrate accounts to the database."""
        from provider.repositories.account_repository import AccountRepository
        repo = AccountRepository(self.db)
        for acc in accounts:
            try:
                repo.create(
                    account_id=acc.account_id,
                    api_key=acc.api_key,
                    base_url=acc.base_url,
                    region="china",
                )
            except Exception:
                pass  # Already exists or constraint error

    @staticmethod
    def get_database_url() -> str:
        """Get database URL from environment variable."""
        return os.getenv("DATABASE_URL", "sqlite:///modelscope_proxy.db")

    @staticmethod
    def get_log_level() -> str:
        """Get log level from environment variable."""
        return os.getenv("LOG_LEVEL", "INFO")
