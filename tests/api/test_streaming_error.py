import json
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from provider.main import create_app

# Provide an account via env so ConfigManager (which starts with db=None) can
# load it during service initialization. The migration logic stores it in the
# test DB, keeping the request path intact.
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
    """Lifespan-aware client so services / admin service are initialized.

    We inject MODELSCOPE_ACCOUNTS_JSON so the (otherwise empty) test DB
    bootstraps a single active account; without it the route fails early with
    'No accounts available for load balancing' before http_client.request is
    even called.
    """
    os.environ["MODELSCOPE_ACCOUNTS_JSON"] = _TEST_ACCOUNTS_JSON
    app = create_app()
    try:
        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("MODELSCOPE_ACCOUNTS_JSON", None)


def test_streaming_error_response_format(client):
    """When upstream returns non-200, the streaming error chunk should be
    OpenAI-compatible with error as an object (not a string)."""

    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = ""
    mock_response.aiter_lines = AsyncMock(return_value=iter([]))

    app = client.app
    http_client = app.state.services["http_client"]
    alias_resolver = app.state.services["alias_resolver"]

    with (
        patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
        patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
    ):
        mock_req.return_value = mock_response
        mock_resolve.return_value = "ap-hy3"  # identity resolution, no network call
        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "ap-hy3",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )

    # Collect SSE chunks from the response
    chunks = []
    for line in resp.iter_lines():
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str and data_str != "[DONE]":
                chunks.append(json.loads(data_str))

    # The error chunk should have error as an object, not a string
    error_chunks = [c for c in chunks if "error" in c]
    assert len(error_chunks) >= 1, "Expected at least one error chunk"
    error_chunk = error_chunks[0]
    error_obj = error_chunk["error"]
    assert isinstance(error_obj, dict), f"Expected error to be a dict, got {type(error_obj)}"
    assert "message" in error_obj
    assert "code" in error_obj
    assert error_obj["code"] == "403"
    assert error_obj["type"] == "server_error"


def test_streaming_error_logs_real_status_code(client):
    """When upstream returns 403 in streaming mode, the log entry should
    record status_code=403 (not 200) and input/output tokens as 0."""

    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = ""
    mock_response.aiter_lines = AsyncMock(return_value=iter([]))

    app = client.app
    http_client = app.state.services["http_client"]
    alias_resolver = app.state.services["alias_resolver"]
    log_repo = app.state.admin_service.log_repo
    logs_before, _ = log_repo.find_all()
    before_ids = {r["id"] for r in logs_before}

    with (
        patch.object(http_client, "request", new_callable=AsyncMock) as mock_req,
        patch.object(alias_resolver, "resolve_alias", new_callable=AsyncMock) as mock_resolve,
    ):
        mock_req.return_value = mock_response
        mock_resolve.return_value = "ap-hy3"  # identity resolution, no network call
        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "ap-hy3",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        # Consume response to trigger logging
        for _ in resp.iter_lines():
            pass

    logs_after, _ = log_repo.find_all()
    assert len(logs_after) > len(logs_before), "Expected a new log entry"

    # Find the new streaming log
    new_streaming = [
        r for r in logs_after
        if r["id"] not in before_ids and r.get("is_stream")
    ]
    assert len(new_streaming) >= 1, "Expected a streaming log entry"
    latest = new_streaming[0]

    assert latest["status_code"] == 403, f"Expected status_code=403, got {latest['status_code']}"
    assert latest["input_tokens"] == 0, f"Expected 0 input tokens on error, got {latest['input_tokens']}"
    assert latest["output_tokens"] == 0, f"Expected 0 output tokens on error, got {latest['output_tokens']}"
