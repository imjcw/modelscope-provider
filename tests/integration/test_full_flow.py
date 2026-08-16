import os
import pytest
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient
from provider.main import create_app
from provider.core.database import DatabaseManager
from provider.core.migrations import Migrator
from provider.repositories.account_repository import AccountRepository


@pytest.fixture
def integration_db_url(tmp_path):
    """Per-test isolated integration DB (tmp_path, auto-cleaned by pytest)."""
    db_path = tmp_path / "integration_test.db"
    url = f"sqlite:///{db_path}"
    os.environ["DATABASE_URL"] = url

    db = DatabaseManager(url)
    db.initialize_tables()
    Migrator(db).run()
    db.close()

    yield url
    # tmp_path 自动清理，无需手动操作


def _seed_test_supplier(db_url: str):
    """Seed a test supplier into the given DB.

    Uses ``AccountRepository.create`` so API keys land in ``account_api_keys``
    (the legacy ``accounts.api_key`` column was dropped in migration 023).
    """
    db = DatabaseManager(db_url)
    repo = AccountRepository(db)
    if not repo.find_all():
        repo.create(
            name="test-integration-000",
            api_keys=["test-integration-key"],
            base_url="https://api-inference.modelscope.cn/v1/chat/completions",
        )


@pytest.fixture
def client(integration_db_url):
    """Test client with lifespan context — services are initialized properly."""
    _seed_test_supplier(integration_db_url)
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.mark.xfail(
    reason="Integration test hits the real ModelScope upstream API which no longer "
           "serves model 'hy3' (returns 404/503). Requires a mock http_client or "
           "a currently-valid model name to be reliable. Pre-existing flakiness.",
    strict=False,
)
def test_full_flow_with_success(client):
    """Test complete flow with successful response."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    response = client.post(
        "/openai/v1/chat/completions",
        json={
            "model": "hy3",
            "messages": [{"role": "user", "content": "Hello"}],
        },
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
    assert "total_suppliers" in data
    assert "quota_status" in data


def test_error_handling_missing_messages(client):
    """Test error handling when messages field is missing."""
    response = client.post(
        "/openai/v1/chat/completions",
        json={"model": "test"},  # Missing messages field
    )
    assert response.status_code == 422


def test_error_handling_missing_model(client):
    """Test error handling when model field is missing."""
    response = client.post(
        "/openai/v1/chat/completions",
        json={"messages": []},  # Missing model field
    )
    assert response.status_code == 422


def test_round_robin_account_selection():
    """Test that load balancer selects accounts in round-robin order."""
    from provider.services.load_balancer import LoadBalancer
    from provider.models.account import ModelScopeAccount

    accounts = [
        ModelScopeAccount(account_id="acc1", api_key="k1", base_url="url1"),
        ModelScopeAccount(account_id="acc2", api_key="k2", base_url="url2"),
        ModelScopeAccount(account_id="acc3", api_key="k3", base_url="url3"),
    ]

    balancer = LoadBalancer(accounts)

    acc1 = balancer.select_account()
    acc2 = balancer.select_account()
    acc3 = balancer.select_account()

    assert acc1.account_id == "acc1"
    assert acc2.account_id == "acc2"
    assert acc3.account_id == "acc3"

    acc4 = balancer.select_account()
    assert acc4.account_id == "acc1"


def test_quota_update_and_mark_unavailable(tmp_path):
    """Test quota update marks model as unavailable when exhausted."""
    from provider.services.quota_updater import QuotaUpdater
    from provider.repositories.quota_repository import QuotaRepository
    from provider.models.account import ModelScopeAccount

    db_path = tmp_path / "test_quota_integration.db"
    db = DatabaseManager(f"sqlite:///{db_path}")
    db.initialize_tables()

    repo = QuotaRepository(db)
    updater = QuotaUpdater(repo)

    account = ModelScopeAccount(
        account_id="test-account",
        api_key="test-key",
        base_url="https://api-inference.modelscope.cn/v1",
    )

    repo.get_or_create_daily_quota("test-account", 100)

    headers = {
        "modelscope-ratelimit-requests-remaining": "0",
        "modelscope-ratelimit-requests-limit": "100",
    }

    updater.update_quota_after_request(account, headers, "hy3")

    info = updater.get_quota_info("test-account")
    assert info is not None
    assert "hy3" in info["unavailable_models"]
    assert info["quota_remaining"] == 0
    assert info["quota_limit"] == 100


def test_response_converter_full_response():
    """Test response converter with full ModelScope response."""
    from provider.services.response_converter import ResponseConverter

    converter = ResponseConverter()

    ms_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677858242,
        "model": "hy3",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": 15,
            "total_tokens": 20,
        },
    }

    openai_response = converter.convert_to_openai(ms_response)

    assert openai_response["id"] == "chatcmpl-123"
    assert openai_response["object"] == "chat.completion"
    assert openai_response["model"] == "hy3"
    assert openai_response["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
    assert openai_response["usage"]["total_tokens"] == 20


@pytest.mark.asyncio
async def test_model_alias_resolver_mock():
    """Test model alias resolver with mocked HTTP client."""
    from provider.models.alias_resolver import ModelAliasResolver
    from provider.models.account import ModelScopeAccount

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=Mock(
        status_code=200,
        json=lambda: {
            "data": [
                {
                    "id": "hy3 overseas",
                    "object": "model",
                    "created": 1234567890,
                    "owned_by": "modelscope",
                }
            ],
            "object": "list",
        },
        raise_for_status=lambda: None,
    ))

    account = ModelScopeAccount(
        account_id="test-account",
        api_key="test-key",
        base_url="https://api.inference.modelscope.cn/v1",
    )

    resolver = ModelAliasResolver(mock_client)

    actual_id = await resolver.resolve_alias(account, "hy3")

    assert actual_id == "hy3 overseas"
