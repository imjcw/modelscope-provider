"""Test fallback behavior when upstream returns errors (400, 500, etc.).

Before the fix, non-streaming requests that got a 400 from the upstream
would NOT fall back to the next candidate because httpx.HTTPStatusError
was not caught by the fallback loop (which only catches HTTPException).
"""
import json
import os
import uuid
from unittest.mock import AsyncMock, patch, Mock

import httpx
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
        RoutingResult(account=account1, model_name="test-model", key_id=0, key_string="key1"),
        RoutingResult(account=account2, model_name="test-model", key_id=1, key_string="key2"),
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
        RoutingResult(account=account1, model_name="test-model", key_id=0, key_string="key1"),
        RoutingResult(account=account2, model_name="test-model", key_id=1, key_string="key2"),
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
        RoutingResult(account=account1, model_name="test-model", key_id=0, key_string="key1"),
        RoutingResult(account=account2, model_name="test-model", key_id=1, key_string="key2"),
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


# ── Streaming fallback tests ────────────────────────────────────────────────


def test_streaming_400_error_triggers_fallback_to_next_candidate(client):
    """When the first candidate returns 400 in streaming mode, the request
    should fall back to the next candidate instead of returning 400 to the
    client. The HTTP request is now made before StreamingResponse is returned,
    so pre-stream errors can trigger fallback.
    """
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
        RoutingResult(account=account1, model_name="test-model", key_id=0, key_string="key1"),
        RoutingResult(account=account2, model_name="test-model", key_id=1, key_string="key2"),
    ]

    # First response: 400 error
    response_400 = Mock()
    response_400.status_code = 400
    response_400.text = '{"error": "Bad Request"}'
    response_400.headers = {}
    # aiter_lines should not be called for the error case (error detected before streaming)

    # Second response: 200 success
    async def _success_lines():
        yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hello!"},"index":0}]}'
        yield "data: [DONE]"

    response_200 = Mock()
    response_200.status_code = 200
    response_200.text = ""
    response_200.headers = {}
    response_200.aiter_lines = _success_lines

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
                "stream": True,
            },
        )

    # Should succeed via fallback to second candidate
    assert resp.status_code == 200, f"Expected 200 after fallback, got {resp.status_code}: {resp.text}"
    assert mock_req.call_count == 2, "Expected 2 HTTP calls (first failed, second succeeded)"


def test_streaming_500_error_triggers_fallback_to_next_candidate(client):
    """When the first candidate returns 500 in streaming mode, the request
    should fall back to the next candidate.
    """
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
        RoutingResult(account=account1, model_name="test-model", key_id=0, key_string="key1"),
        RoutingResult(account=account2, model_name="test-model", key_id=1, key_string="key2"),
    ]

    response_500 = Mock()
    response_500.status_code = 500
    response_500.text = '{"error": "Internal Server Error"}'
    response_500.headers = {}

    async def _success_lines():
        yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hello!"},"index":0}]}'
        yield "data: [DONE]"

    response_200 = Mock()
    response_200.status_code = 200
    response_200.text = ""
    response_200.headers = {}
    response_200.aiter_lines = _success_lines

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
                "stream": True,
            },
        )

    assert resp.status_code == 200, f"Expected 200 after fallback, got {resp.status_code}: {resp.text}"
    assert mock_req.call_count == 2


def test_streaming_all_candidates_fail_returns_error(client):
    """When all streaming candidates fail, should return an error response."""
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
        RoutingResult(account=account1, model_name="test-model", key_id=0, key_string="key1"),
        RoutingResult(account=account2, model_name="test-model", key_id=1, key_string="key2"),
    ]

    response_400 = Mock()
    response_400.status_code = 400
    response_400.text = '{"error": "Bad Request"}'
    response_400.headers = {}
    response_400.aiter_lines = AsyncMock(return_value=iter([]))

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
                "stream": True,
            },
        )

    # All candidates failed — should return 400 (last error)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert mock_req.call_count == 2, "Expected both candidates to be tried"

# ── Network/transport error fallback tests ──────────────────────────────────


def _two_candidates():
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
    return [
        RoutingResult(account=account1, model_name="test-model", key_id=0, key_string="key1"),
        RoutingResult(account=account2, model_name="test-model", key_id=1, key_string="key2"),
    ]


def test_network_error_triggers_fallback_and_records_circuit(client):
    """A connection error on the first candidate should fall back to the next
    candidate AND record a network_error in the circuit breaker (previously it
    bubbled up as an unhandled 500 with no fallback and no circuit recording).
    """
    app = client.app
    http_client = app.state.services["http_client"]
    alias_router = app.state.alias_router
    alias_resolver = app.state.services["alias_resolver"]
    cb = app.state.services["circuit_breaker"]

    candidates = _two_candidates()

    response_200 = Mock()
    response_200.status_code = 200
    response_200.text = '{"id": "chatcmpl-123", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": "Hello!"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}'
    response_200.headers = {}

    connect_error = httpx.ConnectError("Connection refused")

    with (
        patch.object(alias_router, "get_candidates", return_value=candidates),
        patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
        patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
    ):
        mock_req.side_effect = [connect_error, response_200]
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
    assert mock_req.call_count == 2, "Expected fallback to second candidate"
    state = cb.get_state(0, "test-model")
    assert state is not None
    assert state.error_type == "network_error"


def test_timeout_triggers_fallback(client):
    """A timeout on the first candidate should fall back to the next."""
    app = client.app
    http_client = app.state.services["http_client"]
    alias_router = app.state.alias_router
    alias_resolver = app.state.services["alias_resolver"]
    cb = app.state.services["circuit_breaker"]

    candidates = _two_candidates()

    response_200 = Mock()
    response_200.status_code = 200
    response_200.text = '{"id": "chatcmpl-123", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": "Hello!"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}'
    response_200.headers = {}

    timeout_error = httpx.ConnectTimeout("Timed out")

    with (
        patch.object(alias_router, "get_candidates", return_value=candidates),
        patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
        patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
    ):
        mock_req.side_effect = [timeout_error, response_200]
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
    state = cb.get_state(0, "test-model")
    assert state is not None
    assert state.error_type == "network_error"
