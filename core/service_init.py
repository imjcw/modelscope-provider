from typing import List, Optional
from provider.core.config import ConfigManager
from provider.core.database import DatabaseManager
from provider.core.http_client import HttpClient
from provider.models.account import ModelScopeAccount
from provider.models.alias_resolver import ModelAliasResolver
from provider.repositories.quota_repository import QuotaRepository
from provider.services.load_balancer import LoadBalancer
from provider.services.response_converter import ResponseConverter
from provider.services.quota_updater import QuotaUpdater


class ServiceInitializer:
    """Initialize all services."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    async def initialize_all(
        self,
        accounts: Optional[List[ModelScopeAccount]] = None,
    ) -> dict:
        """Initialize all services.

        Args:
            accounts: If provided, use these accounts. Otherwise load from
                      config (DB preferred, .env fallback).

        Returns:
            Dictionary containing initialized services
        """
        # Initialize database
        database = DatabaseManager(self.config.get_database_url())
        database.initialize_tables()
        database.seed_default_config()

        # Load accounts if not provided
        if accounts is None:
            self.config.db = database
            accounts = self.config.load_accounts(migrate_from_env=True)

        # Initialize HTTP client
        http_client = HttpClient()

        # Initialize repositories
        quota_repository = QuotaRepository(database)

        # Initialize services
        load_balancer = LoadBalancer(accounts)
        response_converter = ResponseConverter()
        quota_updater = QuotaUpdater(quota_repository)
        alias_resolver = ModelAliasResolver(await http_client.create_client())

        services = {
            "database": database,
            "http_client": http_client,
            "quota_repository": quota_repository,
            "load_balancer": load_balancer,
            "response_converter": response_converter,
            "quota_updater": quota_updater,
            "alias_resolver": alias_resolver,
            "accounts": accounts
        }

        return services
