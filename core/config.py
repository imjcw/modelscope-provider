import json
import logging
import os
from typing import List, Dict, Optional

from dotenv import load_dotenv
from models.account import ModelScopeAccount, DEFAULT_PROVIDER_TYPE

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
            # Accept `name` (preferred) or fall back to `account_id` for backward compat
            name = account_data.get("name") or account_data.get("account_id", "")
            api_key = account_data.get("api_key")
            base_url = account_data.get("base_url")
            if not api_key or not base_url:
                raise ValueError(
                    f"Account {name!r} is missing required 'api_key' or 'base_url'"
                )
            account = ModelScopeAccount(
                account_id=account_data.get("account_id", ""),
                name=name,
                api_key=api_key,
                base_url=base_url,
                provider_type=account_data.get("provider_type", DEFAULT_PROVIDER_TYPE),
            )
            accounts_list.append(account)

        if not accounts_list:
            raise ValueError("No ModelScope accounts configured")

        return accounts_list

    def load_accounts_from_db(self) -> List[ModelScopeAccount]:
        """Load ModelScope accounts from database."""
        if not self.db:
            raise ValueError("Database not configured, cannot load accounts from DB")

        from repositories.account_repository import AccountRepository
        repo = AccountRepository(self.db)
        db_accounts = repo.find_active()

        if not db_accounts:
            return []

        # Batch-load multi API keys and today's unavailable models so the legacy
        # LoadBalancer path honors key rotation and quota-based exclusion from
        # startup (mirrors refresh_load_balancer in api/routes.py).
        keys_by_id = repo.find_api_keys_by_account_ids([a["id"] for a in db_accounts])
        unavailable_map = {}
        try:
            from repositories.quota_repository import QuotaRepository
            unavailable_map = QuotaRepository(self.db).get_unavailable_models_batch(
                [a["account_id"] for a in db_accounts]
            )
        except Exception:
            unavailable_map = {}

        accounts = []
        for a in db_accounts:
            accounts.append(ModelScopeAccount(
                account_id=a["account_id"],
                name=a.get("name", ""),
                base_url=a["base_url"],
                provider_type=a.get("provider_type", DEFAULT_PROVIDER_TYPE),
                api_key_records=keys_by_id.get(a["id"]) or None,
                unavailable_models=unavailable_map.get(a["account_id"], set()),
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
                # No accounts configured anywhere — OK to start with empty list
                logger.warning(f"No accounts configured (DB empty, env empty): {e}")
                return []

        raise ValueError("No accounts found in database and migration disabled")

    def _migrate_accounts_to_db(self, accounts: List[ModelScopeAccount]):
        """Migrate accounts to the database. account_id is auto-generated as UUID."""
        from repositories.account_repository import AccountRepository
        repo = AccountRepository(self.db)
        for acc in accounts:
            try:
                repo.create(
                    name=acc.name or acc.account_id,
                    api_key=acc.api_key,
                    base_url=acc.base_url,
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
