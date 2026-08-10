"""Regression tests for the request body-size limit middleware (S6).

The middleware enforces a cap on request bodies. The original implementation
only validated ``Content-Length``, so requests sent with
``Transfer-Encoding: chunked`` (no Content-Length header) could bypass the
limit. These tests exercise both the fast path and the chunked branch.
"""
import pytest
from starlette.requests import Request
from starlette.responses import Response

from provider.main import limit_request_body, MAX_REQUEST_BODY


class _FakeReceive:
    """Yield the supplied body chunks exactly once via the ASGI receive hook."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def __call__(self):
        if self._chunks:
            body = self._chunks.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(self._chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}


def _make_request(method, body_chunks, *, content_length=None):
    headers = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": "/openai/v1/chat/completions",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope, receive=_FakeReceive(body_chunks))


async def _call_next_ok(request):
    return Response("ok", status_code=200)


# Use a tiny limit so we can exercise the cap without allocating 16 MB.
TINY_LIMIT = 10


@pytest.fixture(autouse=True)
def tiny_limit(monkeypatch):
    monkeypatch.setattr("provider.main.MAX_REQUEST_BODY", TINY_LIMIT)


async def test_chunked_oversized_rejected():
    """No Content-Length + body over the cap → 413 via the chunked branch."""
    req = _make_request("POST", [b"x" * (TINY_LIMIT + 5)])
    resp = await limit_request_body(req, _call_next_ok)
    assert resp.status_code == 413


async def test_chunked_within_limit_passes():
    """No Content-Length + small body → buffered, then call_next runs (200)."""
    req = _make_request("POST", [b"hello"])
    original_receive = req._receive
    resp = await limit_request_body(req, _call_next_ok)
    assert resp.status_code == 200
    # The chunked branch must have replaced `_receive` with the buffered body.
    assert req._receive is not original_receive


async def test_content_length_oversized_rejected():
    """Oversized Content-Length → 413 on the fast path (no body read)."""
    req = _make_request("POST", [b"x" * (TINY_LIMIT + 1)], content_length=TINY_LIMIT + 1)
    resp = await limit_request_body(req, _call_next_ok)
    assert resp.status_code == 413


async def test_get_without_content_length_skipped():
    """GET has no body → chunked branch is skipped, request passes through."""
    req = _make_request("GET", [])
    resp = await limit_request_body(req, _call_next_ok)
    assert resp.status_code == 200


async def test_chunked_small_body_replaces_receive_once():
    """Multiple small chunks are reassembled into a single buffered body."""
    req = _make_request("POST", [b"aa", b"bb", b"cc"])
    resp = await limit_request_body(req, _call_next_ok)
    assert resp.status_code == 200
    # The replaced `_receive` yields the full reassembled body in one shot.
    message = await req._receive()
    assert message["body"] == b"aabbcc"
    assert message["more_body"] is False


def test_middleware_registered_on_app():
    """The middleware is wired into apps built by create_app (not only lifespan)."""
    from fastapi.testclient import TestClient
    from provider.main import create_app

    app = create_app()
    with TestClient(app) as client:
        # Oversized Content-Length → 413 (proves the middleware is active).
        resp = client.post(
            "/openai/v1/chat/completions",
            content=b"x" * (TINY_LIMIT + 1),
            headers={"Content-Length": str(TINY_LIMIT + 1)},
        )
        assert resp.status_code == 413

        # Small body (well under the tiny test limit) → not blocked by the
        # limiter (endpoint may 422 on schema, but it must not be a 413).
        resp2 = client.post(
            "/openai/v1/chat/completions",
            content=b"{}",
            headers={"Content-Length": "2"},
        )
        assert resp2.status_code != 413
