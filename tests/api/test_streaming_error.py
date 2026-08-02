"""Test streaming error handling.

Before the fix, streaming requests that got a non-200 from the upstream
would yield an SSE error chunk to the client. Now the HTTP request is
made BEFORE returning StreamingResponse, so errors are detected early
and returned as HTTP error responses — enabling fallback to the next
candidate in the alias router path.
"""
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


def test_streaming_error_returns_http_error(client):
    """When upstream returns non-200 in streaming mode, the request should
    return an HTTP error response (not SSE chunks) because the HTTP request
    is now made before StreamingResponse is returned, enabling fallback to
    the next candidate in the alias router path.
    """

    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = ""
    mock_response.aiter_lines = AsyncMock(return_value=iter([]))
    mock_response.headers = {}

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

    # Should return HTTP error (not SSE streaming)
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    body = resp.json()
    # FastAPI wraps HTTPException detail in a "detail" key
    detail = body.get("detail", body)
    assert "error" in detail, f"Expected 'error' in response, got: {body}"
    error_obj = detail["error"]
    assert isinstance(error_obj, dict), f"Expected error to be a dict, got {type(error_obj)}"
    assert "message" in error_obj
    assert "code" in error_obj
    assert error_obj["code"] == "upstream_403"
    assert error_obj["type"] == "upstream_error"


def test_streaming_error_with_single_candidate_logs_error(client):
    """When upstream returns 403 in streaming mode with a single candidate
    (no alias binding), the error is raised before streaming starts, but the
    failed request must still be recorded in the request logs so the admin
    panel shows why it failed. (Regression: failure logging was added in
    ``fix(api): 记录失败请求日志``; older expectation of "no log" is obsolete.)
    """

    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = ""
    mock_response.aiter_lines = AsyncMock(return_value=iter([]))
    mock_response.headers = {}

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
        mock_resolve.return_value = "ap-hy3"
        resp = client.post(
            "/api/v1/chat/completions",
            json={
                "model": "ap-hy3",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )

    # Should return HTTP error
    assert resp.status_code == 403

    logs_after, _ = log_repo.find_all()
    new_streaming = [
        r for r in logs_after
        if r["id"] not in before_ids and r.get("is_stream")
    ]
    # The failed stream request must be logged (status 403), so operators can
    # see why the stream never started.
    assert len(new_streaming) == 1, (
        f"Expected 1 streaming error log entry, got {len(new_streaming)}"
    )
    assert new_streaming[0]["status_code"] == 403
    assert new_streaming[0]["error_message"]