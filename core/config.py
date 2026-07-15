import json
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from provider.models.account import ModelScopeAccount

load_dotenv()


class ConfigManager:
    """Manage configuration from environment variables."""

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

    @staticmethod
    def get_database_url() -> str:
        """Get database URL from environment variable."""
        return os.getenv("DATABASE_URL", "sqlite:///modelscope_proxy.db")

    @staticmethod
    def get_log_level() -> str:
        """Get log level from environment variable."""
        return os.getenv("LOG_LEVEL", "INFO")
