from typing import List, Optional
from core.config import ConfigManager
from core.database import DatabaseManager
from core.http_client import HttpClient
from models.account import ModelScopeAccount
from models.alias_resolver import ModelAliasResolver
from repositories.account_repository import AccountRepository
from repositories.config_repository import ConfigRepository
from repositories.mapping_model_repository import MappingModelRepository
from repositories.mapping_repository import MappingRepository
from repositories.quota_repository import QuotaRepository
from repositories.supplier_model_repository import SupplierModelRepository
from services.alias_router import AliasRouter
from services.cache import ConfigCache, RateLimitCache
from services.circuit_breaker import CircuitBreaker
from services.load_balancer import LoadBalancer
from services.response_converter import ResponseConverter
from services.quota_updater import QuotaUpdater
from services.providers import create_strategy, build_rate_limit_strategies
from repositories.provider_type_repository import ProviderTypeRepository
from core.migrations import Migrator


def _resolve_read_timeout(config_repo) -> float:
    """Read ``request_timeout_ms`` and convert to seconds for httpx read timeout.

    Falls back to 1 hour (3600s) if the key is missing or not a valid number.
    """
    raw = config_repo.get("request_timeout_ms")
    if raw is None:
        return 3600.0
    try:
        return max(0.0, float(raw) / 1000.0)
    except (ValueError, TypeError):
        return 3600.0


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
        # Run schema migrations (idempotent — skips already-applied migrations)
        Migrator(database).run()
        database.seed_default_config()

        # Load accounts if not provided
        if accounts is None:
            self.config.db = database
            accounts = self.config.load_accounts(migrate_from_env=True)

        # Initialize repositories (config first — needed to configure HTTP timeouts)
        config_repo = ConfigRepository(database)

        # Initialize HTTP client — read_timeout is driven by request_timeout_ms
        # (default 1 hour) so slow upstream model responses don't raise ReadTimeout.
        http_client = HttpClient(read_timeout=_resolve_read_timeout(config_repo))

        # Initialize repositories
        quota_repository = QuotaRepository(database)
        mapping_repository = MappingRepository(database)
        supplier_model_repo = SupplierModelRepository(database)
        mapping_model_repo = MappingModelRepository(database)
        account_repo = AccountRepository(database)

        # Initialize in-memory caches
        config_cache = ConfigCache(config_repo)
        rate_limit_cache = RateLimitCache(database)

        # Initialize services
        load_balancer = LoadBalancer(accounts, supplier_model_repo=supplier_model_repo)
        response_converter = ResponseConverter()
        quota_updater = QuotaUpdater(quota_repository)
        alias_resolver = ModelAliasResolver(
            await http_client.create_client(), mapping_repo=mapping_repository
        )
        alias_router = AliasRouter(
            mapping_model_repo=mapping_model_repo,
            account_repo=account_repo,
            config_repo=config_repo,
            config_cache=config_cache,
        )

        # Per-provider rate-limit strategies — driven by provider_types table so
        # that 供应商类型管理 can configure strategy + params per type.
        # 先保证硬编码的内置类型始终可用（不依赖迁移），再叠加 DB 配置。
        rate_limit_strategies = {
            "modelscope": create_strategy(
                "header_based",
                quota_updater=quota_updater,
                quota_repository=quota_repository,
            ),
            "sensetime": create_strategy(
                "fixed_window", db=database, rate_limit_cache=rate_limit_cache,
            ),
        }
        # 从 DB 加载自定义类型，覆盖或补充硬编码策略
        try:
            provider_type_repo = ProviderTypeRepository(database)
            db_types = provider_type_repo.find_all()
            if db_types:
                db_strategies = build_rate_limit_strategies(
                    db_types, database, quota_updater, quota_repository,
                    rate_limit_cache=rate_limit_cache,
                )
                rate_limit_strategies.update(db_strategies)
        except Exception:
            pass

        services = {
            "database": database,
            "http_client": http_client,
            "quota_repository": quota_repository,
            "mapping_repository": mapping_repository,
            "supplier_model_repo": supplier_model_repo,
            "provider_type_repo": provider_type_repo,
            "load_balancer": load_balancer,
            "response_converter": response_converter,
            "quota_updater": quota_updater,
            "alias_resolver": alias_resolver,
            "alias_router": alias_router,
            "accounts": accounts,
            "rate_limit_strategies": rate_limit_strategies,
            "circuit_breaker": CircuitBreaker(),
            "config_cache": config_cache,
            "rate_limit_cache": rate_limit_cache,
        }

        return services
