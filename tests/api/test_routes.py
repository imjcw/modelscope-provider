import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from provider.main import create_app
from provider.api.routes import (
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
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_chat_completions_requires_messages(client):
    """Chat completions must reject missing messages (422)."""
    response = client.post(
        "/api/v1/chat/completions",
        json={"model": "test"}
    )
    assert response.status_code == 422


def test_chat_completions_requires_model(client):
    """Chat completions must reject missing model (422)."""
    response = client.post(
        "/api/v1/chat/completions",
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
