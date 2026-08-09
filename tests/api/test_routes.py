import asyncio
import json
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from provider.main import create_app
from provider.api.openai_routes import (
    _extract_cache_usage,
    stream_response_with_logging,
)


@pytest.fixture()
def client():
    """Lifespan-aware client so services / admin service are initialized."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_chat_completions_requires_messages(client):
    """Chat completions must reject missing messages (422)."""
    response = client.post(
        "/openai/v1/chat/completions",
        json={"model": "test"}
    )
    assert response.status_code == 422


def test_chat_completions_requires_model(client):
    """Chat completions must reject missing model (422)."""
    response = client.post(
        "/openai/v1/chat/completions",
        json={"messages": []}
    )
    assert response.status_code == 422


def test_admin_quota_endpoint_present(client):
    """The /api/admin/quota placeholder endpoint returns 200."""
    response = client.get("/api/admin/quota")
    assert response.status_code == 200
    data = response.json()
    assert "total_suppliers" in data
    assert "quota_status" in data


def test_list_models_endpoint_present(client, monkeypatch):
    """OpenAI-compatible /api/v1/models returns a list object."""
    from provider.api import openai_routes as routes_mod

    fake_repo = Mock()
    fake_repo.find_all.return_value = [
        {"alias_name": "hy3", "actual_model_id": "hy3-actual", "description": "", "status": "active"},
        {"alias_name": "qwen2.5", "actual_model_id": "qwen-actual", "description": "", "status": "active"},
        {"alias_name": "disabled-model", "actual_model_id": "x", "description": "", "status": "disabled"},
    ]
    fake_admin = Mock()
    fake_admin.mapping_repo = fake_repo
    monkeypatch.setattr(routes_mod, "get_admin_service", lambda req: fake_admin)

    response = client.get("/openai/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    for model in data["data"]:
        assert "id" in model
        assert model["object"] == "model"
        assert model["owned_by"] == "provider"


def test_list_models_returns_configured_aliases(client, monkeypatch):
    """Listed model ids correspond to configured mapping aliases (dicts)."""
    from provider.api import openai_routes as routes_mod

    fake_repo = Mock()
    fake_repo.find_all.return_value = [
        {"alias_name": "hy3", "actual_model_id": "hy3-actual", "description": "", "status": "active"},
        {"alias_name": "qwen2.5", "actual_model_id": "qwen-actual", "description": "", "status": "active"},
        {"alias_name": "disabled-model", "actual_model_id": "x", "description": "", "status": "disabled"},
    ]
    fake_admin = Mock()
    fake_admin.mapping_repo = fake_repo
    monkeypatch.setattr(routes_mod, "get_admin_service", lambda req: fake_admin)

    response = client.get("/openai/v1/models")
    assert response.status_code == 200
    models = response.json()["data"]
    ids = [m["id"] for m in models]
    # disabled models must be excluded; active aliases are listed
    assert ids == ["hy3", "qwen2.5"]
    assert all(isinstance(i, str) and i for i in ids)


# ---------------------------------------------------------------------------
# _extract_cache_usage unit tests
# ---------------------------------------------------------------------------

def test_extract_cache_usage_openai_style():
    """OpenAI style: prompt_tokens_details.cached_tokens."""
    usage = {
        "prompt_tokens": 83919,
        "completion_tokens": 436,
        "prompt_tokens_details": {"cached_tokens": 81920, "audio_tokens": 0},
    }
    assert _extract_cache_usage(usage) == (81920, 0)


def test_extract_cache_usage_partial_cached():
    """prompt_partial_cached_tokens inside prompt_tokens_details."""
    usage = {
        "prompt_tokens_details": {
            "cached_tokens": 100,
            "prompt_partial_cached_tokens": 50,
        },
    }
    assert _extract_cache_usage(usage) == (100, 50)


def test_extract_cache_usage_deepseek_style():
    """DeepSeek style: prompt_cache_hit_tokens at usage top level."""
    usage = {
        "prompt_tokens": 1000,
        "prompt_cache_hit_tokens": 768,
        "prompt_cache_miss_tokens": 232,
    }
    assert _extract_cache_usage(usage) == (768, 0)


def test_extract_cache_usage_deepseek_fallback_when_details_empty():
    """Top-level prompt_cache_hit_tokens used when details lack cached_tokens."""
    usage = {
        "prompt_cache_hit_tokens": 512,
        "prompt_tokens_details": {"audio_tokens": 0},
    }
    assert _extract_cache_usage(usage) == (512, 0)


def test_extract_cache_usage_empty_and_none():
    """Missing/None usage or details must not raise."""
    assert _extract_cache_usage(None) == (0, 0)
    assert _extract_cache_usage({}) == (0, 0)
    assert _extract_cache_usage({"prompt_tokens_details": None}) == (0, 0)
    assert _extract_cache_usage(
        {"prompt_tokens_details": {"cached_tokens": None}}
    ) == (0, 0)


def test_extract_cache_usage_invalid_values():
    """Non-numeric values degrade to zero instead of raising."""
    assert _extract_cache_usage(
        {"prompt_tokens_details": {"cached_tokens": "abc"}}
    ) == (0, 0)


# ---------------------------------------------------------------------------
# Streaming path: cached_tokens must reach admin_service.log_request
# ---------------------------------------------------------------------------

class _FakeStreamResponse:
    """Minimal stand-in for an httpx streaming response."""

    def __init__(self, lines):
        self._lines = lines
        self.headers = {"content-type": "text/event-stream"}

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeAccount:
    account_id = "acc-1"
    name = "test-account"


@pytest.mark.asyncio
async def test_stream_logging_records_cached_tokens():
    """Streaming wrapper must extract cached_tokens from the final usage chunk."""
    usage_chunk = {
        "choices": [],
        "usage": {
            "prompt_tokens": 83919,
            "completion_tokens": 436,
            "total_tokens": 84355,
            "prompt_tokens_details": {"cached_tokens": 81920, "audio_tokens": 0},
        },
    }
    lines = [
        'data: {"choices":[{"delta":{"content":"hi"},"index":0}]}',
        f"data: {json.dumps(usage_chunk)}",
        "data: [DONE]",
    ]
    admin_service = Mock()

    chunks = []
    async for chunk in stream_response_with_logging(
        response=_FakeStreamResponse(lines),
        account=_FakeAccount(),
        model_name="test-model",
        request_body={"model": "test-model", "messages": []},
        actual_model_id="vendor/test-model",
        admin_service=admin_service,
        request_start="2026-07-27T00:00:00+00:00",
    ):
        chunks.append(chunk)

    # Client still receives the raw chunks (pass-through untouched)
    assert any("81920" in c for c in chunks)

    admin_service.log_request.assert_called_once()
    kwargs = admin_service.log_request.call_args.kwargs
    assert kwargs["input_tokens"] == 83919
    assert kwargs["output_tokens"] == 436
    assert kwargs["cached_tokens"] == 81920
    assert kwargs["prompt_partial_cached"] == 0


@pytest.mark.asyncio
async def test_stream_logging_no_cache_data_defaults_zero():
    """Without cache info in usage, cached_tokens should stay 0."""
    usage_chunk = {
        "choices": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    lines = [
        f"data: {json.dumps(usage_chunk)}",
        "data: [DONE]",
    ]
    admin_service = Mock()

    async for _ in stream_response_with_logging(
        response=_FakeStreamResponse(lines),
        account=_FakeAccount(),
        model_name="test-model",
        request_body={"model": "test-model", "messages": []},
        actual_model_id="vendor/test-model",
        admin_service=admin_service,
        request_start="2026-07-27T00:00:00+00:00",
    ):
        pass

    kwargs = admin_service.log_request.call_args.kwargs
    assert kwargs["cached_tokens"] == 0
    assert kwargs["prompt_partial_cached"] == 0


# ---------------------------------------------------------------------------
# Interrupted streams must still produce a request log entry
# ---------------------------------------------------------------------------
# Regression: stream_response_with_logging only logged AFTER the stream
# completed normally. Upstream mid-stream failures, client disconnects
# (CancelledError / GeneratorExit) silently produced NO log entry — the admin
# panel only saw a subset of the streams that were actually started.

class _BrokenStreamResponse:
    """Streaming response whose upstream connection dies mid-stream."""

    def __init__(self, fail_at: int = 1):
        self._fail_at = fail_at
        self._count = 0
        self.headers = {"content-type": "text/event-stream"}

    async def aiter_lines(self):
        yield 'data: {"choices":[{"delta":{"content":"hi"},"index":0}]}'
        self._count += 1
        if self._count >= self._fail_at:
            raise httpx.ReadError("connection closed mid-stream")
        yield "data: [DONE]"


@pytest.mark.asyncio
async def test_stream_logging_on_upstream_interrupt():
    """Upstream breaking mid-stream must still write a request log entry."""
    admin_service = Mock()

    with pytest.raises(httpx.ReadError):
        async for _ in stream_response_with_logging(
            response=_BrokenStreamResponse(),
            account=_FakeAccount(),
            model_name="test-model",
            request_body={"model": "test-model", "messages": []},
            actual_model_id="vendor/test-model",
            admin_service=admin_service,
            request_start="2026-07-27T00:00:00+00:00",
        ):
            pass

    admin_service.log_request.assert_called_once()
    kwargs = admin_service.log_request.call_args.kwargs
    assert kwargs["is_stream"] is True
    assert kwargs["status_code"] == -1, "Interrupted stream should be logged as a failure"
    assert "interrupted" in (kwargs.get("error_message") or "").lower()


@pytest.mark.asyncio
async def test_stream_logging_on_client_disconnect_cancelled():
    """Client disconnect surfacing as CancelledError must still be logged."""
    admin_service = Mock()

    class _DisconnectedStream:
        headers = {"content-type": "text/event-stream"}

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"hi"},"index":0}]}'
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        async for _ in stream_response_with_logging(
            response=_DisconnectedStream(),
            account=_FakeAccount(),
            model_name="test-model",
            request_body={"model": "test-model", "messages": []},
            actual_model_id="vendor/test-model",
            admin_service=admin_service,
            request_start="2026-07-27T00:00:00+00:00",
        ):
            pass

    admin_service.log_request.assert_called_once()
    kwargs = admin_service.log_request.call_args.kwargs
    assert kwargs["is_stream"] is True
    assert kwargs["status_code"] == -1
    assert "client disconnected" in (kwargs.get("error_message") or "").lower()


@pytest.mark.asyncio
async def test_stream_logging_on_generator_exit():
    """aclose() (GeneratorExit) mid-stream must still be logged."""
    admin_service = Mock()
    gen = stream_response_with_logging(
        response=_FakeStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"hi"},"index":0}]}',
                "data: [DONE]",
            ]
        ),
        account=_FakeAccount(),
        model_name="test-model",
        request_body={"model": "test-model", "messages": []},
        actual_model_id="vendor/test-model",
        admin_service=admin_service,
        request_start="2026-07-27T00:00:00+00:00",
    )

    # Consume one chunk, then simulate client disconnect via aclose()
    async for _ in gen:
        break
    await gen.aclose()

    admin_service.log_request.assert_called_once()
    kwargs = admin_service.log_request.call_args.kwargs
    assert kwargs["is_stream"] is True
    assert kwargs["status_code"] == -1
    assert "client disconnected" in (kwargs.get("error_message") or "").lower()
