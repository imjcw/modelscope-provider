import datetime
import os
import sqlite3
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient
from provider.main import create_app
import asyncio


class MockAccount:
    """Mock ModelScopeAccount for testing."""
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.name = account_id
        self.base_url = "https://api.inference.modelscope.cn/v1"
        self.api_key = "test-key"
        self.unavailable_models = set()
        self.last_reset_date = "2026-07-15"


# ── 集成测试使用独立数据库，绝不触碰 .env 指向的库 ──
INTEGRATION_DB = Path(__file__).resolve().parent / "integration_test.db"
_INTEGRATION_DB_URL = f"sqlite:///{INTEGRATION_DB}"
_original_env = os.environ.get("DATABASE_URL")


def _get_integration_db_path():
    """Return the integration test DB path (same file, always accessible)."""
    return str(INTEGRATION_DB)


def _ensure_test_supplier_in_db():
    """Directly seed a supplier into the integration test DB."""
    db_path = _get_integration_db_path()
    # Ensure tables exist
    from provider.core.database import DatabaseManager
    db = DatabaseManager(_INTEGRATION_DB_URL)
    db.initialize_tables()

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM accounts")
    if c.fetchone()[0] > 0:
        conn.close()
        return
    c.execute("PRAGMA table_info(accounts)")
    cols = {row[1] for row in c.fetchall()}
    if "name" in cols:
        c.execute(
            "INSERT INTO accounts (account_id, name, api_key, base_url, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("test-integration-000", "test-integration-000",
             "test-integration-key",
             "https://api-inference.modelscope.cn/v1/chat/completions",
             "active"),
        )
    else:
        c.execute(
            "INSERT INTO accounts (account_id, api_key, base_url, status) "
            "VALUES (?, ?, ?, ?)",
            ("test-integration-000", "test-integration-key",
             "https://api-inference.modelscope.cn/v1/chat/completions",
             "active"),
        )
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def integration_db_isolation():
    """Override DATABASE_URL for integration tests so they never touch the .env DB."""
    os.environ["DATABASE_URL"] = _INTEGRATION_DB_URL
    yield
    # Restore original env
    if _original_env is not None:
        os.environ["DATABASE_URL"] = _original_env
    elif "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]
    # Clean up integration DB after all tests
    if INTEGRATION_DB.exists():
        INTEGRATION_DB.unlink()


@pytest.fixture
def client():
    _ensure_test_supplier_in_db()
    app = create_app()
    c = TestClient(app)
    yield c
    c.close()


def test_full_flow_with_success(client):
    """Test complete flow with successful response."""
    # Make a request to the health check
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    # Make a request to chat completions
    response = client.post(
        "/api/v1/chat/completions",
        json={
            "model": "hy3",
            "messages": [{"role": "user", "content": "Hello"}]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "choices" in data
    assert data["choices"][0]["message"]["role"] == "assistant"


def test_full_flow_with_admin_quota(client):
    """Test admin quota endpoint returns valid data."""
    response = client.get("/api/admin/quota")
    assert response.status_code == 200
    data = response.json()
    assert "total_accounts" in data
    assert "quota_status" in data


def test_error_handling_missing_messages(client):
    """Test error handling when messages field is missing."""
    response = client.post(
        "/api/v1/chat/completions",
        json={"model": "test"}  # Missing messages field
    )
    # FastAPI should return 422 for validation error
    assert response.status_code == 422


def test_error_handling_missing_model(client):
    """Test error handling when model field is missing."""
    response = client.post(
        "/api/v1/chat/completions",
        json={"messages": []}  # Missing model field
    )
    # FastAPI should return 422 for validation error
    assert response.status_code == 422


def test_round_robin_account_selection():
    """Test that load balancer selects accounts in round-robin order."""
    from provider.services.load_balancer import LoadBalancer
    from provider.models.account import ModelScopeAccount

    accounts = [
        ModelScopeAccount(account_id="acc1", api_key="k1", base_url="url1"),
        ModelScopeAccount(account_id="acc2", api_key="k2", base_url="url2"),
        ModelScopeAccount(account_id="acc3", api_key="k3", base_url="url3")
    ]

    balancer = LoadBalancer(accounts)

    # Should select in round-robin order
    acc1 = balancer.select_account()
    acc2 = balancer.select_account()
    acc3 = balancer.select_account()

    assert acc1.account_id == "acc1"
    assert acc2.account_id == "acc2"
    assert acc3.account_id == "acc3"

    # Should wrap around
    acc4 = balancer.select_account()
    assert acc4.account_id == "acc1"


def test_quota_update_and_mark_unavailable():
    """Test quota update marks model as unavailable when exhausted."""
    from provider.services.quota_updater import QuotaUpdater
    from provider.repositories.quota_repository import QuotaRepository
    from provider.core.database import DatabaseManager
    from provider.models.account import ModelScopeAccount

    # Create database manager (use a temp file, cleaned up after test)
    _quota_db_path = Path(__file__).resolve().parent / "test_quota_integration.db"
    db = DatabaseManager(f"sqlite:///{_quota_db_path}")
    db.initialize_tables()

    # Create quota repository
    repo = QuotaRepository(db)

    # Create quota updater
    updater = QuotaUpdater(repo)

    # Create account
    account = ModelScopeAccount(
        account_id="test-account",
        api_key="test-key",
        base_url="https://api.inference.modelscope.cn/v1"
    )

    # First create the quota entry with limit=100
    repo.get_or_create_daily_quota("test-account", 100)

    # Simulate quota exhaustion
    headers = {
        "modelscope-ratelimit-requests-remaining": "0",
        "modelscope-ratelimit-requests-limit": "100"
    }

    updater.update_quota_after_request(account, headers, "hy3")

    # Verify model is marked as unavailable
    info = updater.get_quota_info("test-account")
    assert info is not None
    assert "hy3" in info["unavailable_models"]
    assert info["quota_remaining"] == 0
    assert info["quota_limit"] == 100

    # Cleanup
    if _quota_db_path.exists():
        _quota_db_path.unlink()


def test_response_converter_full_response():
    """Test response converter with full ModelScope response."""
    from provider.services.response_converter import ResponseConverter

    converter = ResponseConverter()

    ms_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677858242,
        "model": "hy3",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you today?"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 15,
            "total_tokens": 20
        }
    }

    openai_response = converter.convert_to_openai(ms_response)

    assert openai_response["id"] == "chatcmpl-123"
    assert openai_response["object"] == "chat.completion"
    assert openai_response["model"] == "hy3"
    assert openai_response["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
    assert openai_response["usage"]["total_tokens"] == 20


def test_model_alias_resolver_mock():
    """Test model alias resolver with mocked HTTP client."""
    import httpx
    from provider.models.alias_resolver import ModelAliasResolver
    from provider.models.account import ModelScopeAccount

    # Create mock HTTP client
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=Mock(
        status_code=200,
        json=lambda: {
            "data": [{
                "id": "hy3 overseas",
                "object": "model",
                "created": 1234567890,
                "owned_by": "modelscope"
            }],
            "object": "list"
        },
        raise_for_status=lambda: None
    ))

    # Create account
    account = ModelScopeAccount(
        account_id="test-account",
        api_key="test-key",
        base_url="https://api.inference.modelscope.cn/v1"
    )

    # Create resolver
    resolver = ModelAliasResolver(mock_client)

    # Resolve alias (async)
    actual_id = asyncio.run(resolver.resolve_alias(account, "hy3"))

    # Verify result
    assert actual_id == "hy3 overseas"
