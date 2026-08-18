"""Performance tests for optimized API routes."""
import pytest
from unittest.mock import Mock, patch
from provider.api.openai_routes import get_services, refresh_load_balancer
from provider.services.circuit_breaker import CircuitBreaker
from provider.services.providers.sensetime import SenseTimeStrategy
from provider.services.providers.per_model import PerModelFixedWindowStrategy
from provider.services.providers.modelscope import ModelScopeStrategy


def test_get_services_returns_services_without_rebuilding_load_balancer():
    """Test that get_services doesn't rebuild LoadBalancer on every call.

    Before optimization, get_services() queried the database and rebuilt
    the LoadBalancer on every request. This test verifies the LoadBalancer
    is returned as-is from app state.
    """
    # 创建模拟的 AccountRepository 返回一个真实账户
    mock_account = {
        "account_id": "acc-test",
        "name": "Test Supplier",
        "api_key": "key-test",
        "base_url": "https://api.test.com",
        "provider_type": "modelscope",
    }

    mock_load_balancer = Mock()
    mock_load_balancer.accounts = [mock_account]
    mock_services = {
        "database": Mock(),
        "supplier_model_repo": Mock(),  # 非 None — 旧代码会触发重建
        "load_balancer": mock_load_balancer,
    }

    # 创建模拟的 request
    mock_request = Mock()
    mock_request.app.state.services = mock_services

    # 调用 get_services
    services = get_services(mock_request)

    # 验证：返回的 services 与传入的相同
    assert services is mock_services

    # 验证：LoadBalancer 没有被替换（优化后不应重建）
    assert services["load_balancer"] is mock_load_balancer


def test_refresh_load_balancer_replaces_load_balancer():
    """Test that refresh_load_balancer rebuilds LoadBalancer from DB."""
    # 创建模拟账户数据
    mock_db_accounts = [
        {
            "id": 1,
            "account_id": "acc-1",
            "name": "Supplier 1",
            "api_key": "key1",
            "base_url": "https://api.test1.com",
            "provider_type": "modelscope",
        },
        {
            "id": 2,
            "account_id": "acc-2",
            "name": "Supplier 2",
            "api_key": "key2",
            "base_url": "https://api.test2.com",
            "provider_type": "modelscope",
        },
    ]

    old_load_balancer = Mock()
    mock_services = {
        "database": Mock(),
        "supplier_model_repo": Mock(),
        "load_balancer": old_load_balancer,
    }

    mock_request = Mock()
    mock_request.app.state.services = mock_services

    # 模拟 AccountRepository
    with patch("repositories.account_repository.AccountRepository") as MockAccountRepo:
        mock_repo_instance = Mock()
        mock_repo_instance.find_active.return_value = mock_db_accounts
        mock_repo_instance.find_api_keys_by_account_ids.return_value = {}
        MockAccountRepo.return_value = mock_repo_instance

        # 调用 refresh_load_balancer
        refresh_load_balancer(mock_request)

        # 验证：LoadBalancer 被替换为新实例
        new_lb = mock_services["load_balancer"]
        assert new_lb is not old_load_balancer
        assert new_lb.__class__.__name__ == "LoadBalancer"
        assert len(new_lb.accounts) == 2
        assert new_lb.accounts[0].account_id == "acc-1"
        assert new_lb.accounts[1].account_id == "acc-2"


def test_refresh_load_balancer_handles_errors_gracefully():
    """Test that refresh_load_balancer doesn't crash on errors."""
    mock_services = {
        "database": Mock(),
        "supplier_model_repo": Mock(),
        "load_balancer": Mock(),
    }

    mock_request = Mock()
    mock_request.app.state.services = mock_services

    # 模拟 AccountRepository 抛出异常
    with patch("repositories.account_repository.AccountRepository") as MockAccountRepo:
        mock_repo_instance = Mock()
        mock_repo_instance.find_active.side_effect = Exception("DB error")
        MockAccountRepo.return_value = mock_repo_instance

        old_lb = mock_services["load_balancer"]

        # 不应抛出异常
        refresh_load_balancer(mock_request)

        # LoadBalancer 不应被替换
        assert mock_services["load_balancer"] is old_lb


def test_get_services_raises_503_when_services_none():
    """Test that get_services raises 503 when services is None."""
    from fastapi import HTTPException

    mock_request = Mock()
    mock_request.app.state.services = None

    with pytest.raises(HTTPException) as exc_info:
        get_services(mock_request)
    assert exc_info.value.status_code == 503


def test_refresh_load_balancer_updates_circuit_breaker_resolvers():
    """After refresh, the circuit-breaker window-mode resolvers are rebuilt from
    the refreshed accounts so count-window models take effect without a restart.
    """
    mock_db_accounts = [
        {
            "id": 1,
            "account_id": "acc-sensetime",
            "name": "ST",
            "api_key": "k1",
            "base_url": "https://st.test",
            "provider_type": "sensetime",
        },
        {
            "id": 2,
            "account_id": "acc-per-model",
            "name": "PM",
            "api_key": "k2",
            "base_url": "https://pm.test",
            "provider_type": "pt-per-model",
        },
        {
            "id": 3,
            "account_id": "acc-modelscope",
            "name": "MS",
            "api_key": "k3",
            "base_url": "https://ms.test",
            "provider_type": "modelscope",
        },
    ]

    circuit_breaker = CircuitBreaker()
    rate_limit_strategies = {
        "sensetime": SenseTimeStrategy(db=Mock(), window_seconds=18000, max_requests=1500),
        "pt-per-model": PerModelFixedWindowStrategy(
            db=Mock(),
            model_configs={"m1": {"window_seconds": 600, "max_requests": 5}},
        ),
        "modelscope": ModelScopeStrategy(quota_updater=Mock(), quota_repository=Mock()),
    }

    mock_services = {
        "database": Mock(),
        "supplier_model_repo": Mock(),
        "load_balancer": Mock(),
        "circuit_breaker": circuit_breaker,
        "rate_limit_strategies": rate_limit_strategies,
    }
    mock_request = Mock()
    mock_request.app.state.services = mock_services

    # Before refresh the resolvers are unset.
    assert circuit_breaker.window_mode_resolver is None

    with patch("repositories.account_repository.AccountRepository") as MockAccountRepo:
        mock_repo_instance = Mock()
        mock_repo_instance.find_active.return_value = mock_db_accounts
        mock_repo_instance.find_api_keys_by_account_ids.return_value = {}
        MockAccountRepo.return_value = mock_repo_instance

        refresh_load_balancer(mock_request)

    # After refresh the resolvers reflect the refreshed account set, aligned
    # with the rebuilt LoadBalancer.
    assert circuit_breaker.window_mode_resolver("acc-sensetime", "m1") == "count"
    assert circuit_breaker.window_mode_resolver("acc-per-model", "m1") == "count"
    assert circuit_breaker.window_mode_resolver("acc-modelscope", "m1") == "token"
    # Per-model window override is honoured for escalated-freeze capping.
    assert circuit_breaker.window_seconds_resolver("acc-per-model", "m1") == 600.0
    assert circuit_breaker.window_seconds_resolver("acc-sensetime", "x") == 18000.0