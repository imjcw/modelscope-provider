"""Test fallback behavior when upstream returns errors (400, 500, etc.).

Before the fix, non-streaming requests that got a 400 from the upstream
would NOT fall back to the next candidate because httpx.HTTPStatusError
was not caught by the fallback loop (which only catches HTTPException).
"""
import json
import os
import uuid
from unittest.mock import AsyncMock, patch, Mock

import pytest
from fastapi.testclient import TestClient

from provider.main import create_app

_TEST_ACCOUNTS_JSON = json.dumps(
    [
        {
            "account_id": "test-acc-" + uuid.uuid4().hex[:8],
            "name": "test-account",
            "api_key": "test-key",
            "base_url": "https://api.modelscope.test/v1",
        }
    ]
)


@pytest.fixture()
def client():
    """Lifespan-aware client so services / admin service are initialized."""
    os.environ["MODELSCOPE_ACCOUNTS_JSON"] = _TEST_ACCOUNTS_JSON
    app = create_app()
    try:
        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("MODELSCOPE_ACCOUNTS_JSON", None)


def test_400_error_triggers_fallback_to_next_candidate(client):
    """When the first candidate returns 400, the request should fall back
    to the next candidate instead of returning 400 to the client.
    """
    app = client.app
    http_client = app.state.services["http_client"]
    alias_router = app.state.alias_router
    alias_resolver = app.state.services["alias_resolver"]

    # Create mock candidates
    account1 = Mock()
    account1.account_id = "acc-1"
    account1.name = "Supplier 1"
    account1.api_key = "key1"
    account1.base_url = "https://api1.test.com"
    account1.provider_type = "modelscope"

    account2 = Mock()
    account2.account_id = "acc-2"
    account2.name = "Supplier 2"
    account2.api_key = "key2"
    account2.base_url = "https://api2.test.com"
    account2.provider_type = "modelscope"

    from provider.services.alias_router import RoutingResult
    candidates = [
        RoutingResult(account=account1, model_name="test-model"),
        RoutingResult(account=account2, model_name="test-model"),
    ]

    # Mock responses: first returns 400, second returns 200
    response_400 = Mock()
    response_400.status_code = 400
    response_400.text = '{"error": "Bad Request"}'
    response_400.headers = {}

    response_200 = Mock()
    response_200.status_code = 200
    response_200.text = '{"id": "chatcmpl-123", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": "Hello!"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}'
    response_200.headers = {}

    with (
        patch.object(alias_router, "get_candidates", return_value=candidates),
        patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
        patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
    ):
        # First call returns 400, second returns 200
        mock_req.side_effect = [response_400, response_200]
        mock_resolve.return_value = "test-model"

        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )

    # Should succeed via fallback to second candidate
    assert resp.status_code == 200, f"Expected 200 after fallback, got {resp.status_code}: {resp.text}"
    assert mock_req.call_count == 2, "Expected 2 HTTP calls (first failed, second succeeded)"


def test_500_error_triggers_fallback_to_next_candidate(client):
    """When the first candidate returns 500, the request should fall back."""
    app = client.app
    http_client = app.state.services["http_client"]
    alias_router = app.state.alias_router
    alias_resolver = app.state.services["alias_resolver"]

    account1 = Mock()
    account1.account_id = "acc-1"
    account1.name = "Supplier 1"
    account1.api_key = "key1"
    account1.base_url = "https://api1.test.com"
    account1.provider_type = "modelscope"

    account2 = Mock()
    account2.account_id = "acc-2"
    account2.name = "Supplier 2"
    account2.api_key = "key2"
    account2.base_url = "https://api2.test.com"
    account2.provider_type = "modelscope"

    from provider.services.alias_router import RoutingResult
    candidates = [
        RoutingResult(account=account1, model_name="test-model"),
        RoutingResult(account=account2, model_name="test-model"),
    ]

    response_500 = Mock()
    response_500.status_code = 500
    response_500.text = '{"error": "Internal Server Error"}'
    response_500.headers = {}

    response_200 = Mock()
    response_200.status_code = 200
    response_200.text = '{"id": "chatcmpl-123", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": "Hello!"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}'
    response_200.headers = {}

    with (
        patch.object(alias_router, "get_candidates", return_value=candidates),
        patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
        patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
    ):
        mock_req.side_effect = [response_500, response_200]
        mock_resolve.return_value = "test-model"

        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )

    assert resp.status_code == 200, f"Expected 200 after fallback, got {resp.status_code}: {resp.text}"
    assert mock_req.call_count == 2


def test_all_candidates_fail_returns_error(client):
    """When all candidates fail, should return an error response."""
    app = client.app
    http_client = app.state.services["http_client"]
    alias_router = app.state.alias_router
    alias_resolver = app.state.services["alias_resolver"]

    account1 = Mock()
    account1.account_id = "acc-1"
    account1.name = "Supplier 1"
    account1.api_key = "key1"
    account1.base_url = "https://api1.test.com"
    account1.provider_type = "modelscope"

    account2 = Mock()
    account2.account_id = "acc-2"
    account2.name = "Supplier 2"
    account2.api_key = "key2"
    account2.base_url = "https://api2.test.com"
    account2.provider_type = "modelscope"

    from provider.services.alias_router import RoutingResult
    candidates = [
        RoutingResult(account=account1, model_name="test-model"),
        RoutingResult(account=account2, model_name="test-model"),
    ]

    response_400 = Mock()
    response_400.status_code = 400
    response_400.text = '{"error": "Bad Request"}'
    response_400.headers = {}

    with (
        patch.object(alias_router, "get_candidates", return_value=candidates),
        patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
        patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
    ):
        # Both candidates return 400
        mock_req.return_value = response_400
        mock_resolve.return_value = "test-model"

        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )

    # All candidates failed — should return 400 (last error)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert mock_req.call_count == 2, "Expected both candidates to be tried"