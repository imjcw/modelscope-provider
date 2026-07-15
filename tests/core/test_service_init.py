import pytest
from unittest.mock import AsyncMock, Mock, patch
from provider.core.service_init import ServiceInitializer


class MockAccount:
    """Mock ModelScopeAccount for testing."""
    def __init__(self, account_id: str):
        self.account_id = account_id


@pytest.mark.asyncio
async def test_initialize_all_services():
    """Test initializing all services."""
    with patch("provider.core.service_init.DatabaseManager") as mock_db, \
         patch("provider.core.service_init.HttpClient") as mock_http, \
         patch("provider.core.service_init.QuotaRepository"), \
         patch("provider.core.service_init.LoadBalancer"), \
         patch("provider.core.service_init.ResponseConverter"), \
         patch("provider.core.service_init.QuotaUpdater"), \
         patch("provider.core.service_init.ModelAliasResolver") as mock_resolver:

        mock_db_instance = Mock()
        mock_db_instance.initialize_tables = Mock()
        mock_db_instance.get_today_date = Mock(return_value="2026-07-15")
        mock_db.return_value = mock_db_instance

        mock_http_instance = Mock()
        mock_http_instance.create_client = AsyncMock()
        mock_http_instance.close = AsyncMock()
        mock_http.return_value = mock_http_instance

        mock_resolver_instance = Mock()
        mock_resolver_instance.resolve_alias = AsyncMock(return_value="test-model")
        mock_resolver.return_value = mock_resolver_instance

        accounts = [MockAccount("test_account")]

        config = Mock()
        config.get_database_url = Mock(return_value="sqlite:///test.db")

        initializer = ServiceInitializer(config)
        services = await initializer.initialize_all(accounts)

        assert "database" in services
        assert "http_client" in services
        assert "quota_repository" in services
        assert "load_balancer" in services
        assert "response_converter" in services
        assert "quota_updater" in services
        assert "alias_resolver" in services
        assert "accounts" in services


@pytest.mark.asyncio
async def test_initialize_services_calls_database_init():
    """Test that database initialization is called."""
    with patch("provider.core.service_init.DatabaseManager") as mock_db:
        mock_db_instance = Mock()
        mock_db.return_value = mock_db_instance

        config = Mock()
        config.get_database_url = Mock(return_value="sqlite:///test.db")

        initializer = ServiceInitializer(config)
        accounts = [MockAccount("test_account")]

        await initializer.initialize_all(accounts)

        mock_db_instance.initialize_tables.assert_called_once()
