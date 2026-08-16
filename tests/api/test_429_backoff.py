"""Unit tests for upstream 429 retry-with-backoff.

Targets ``api.anthropic_adapters.request_with_429_backoff`` and its
``Retry-After`` parser. No database / network required.
"""
import asyncio

import pytest

from api.anthropic_adapters import (
    parse_retry_after,
    request_with_429_backoff,
    UPSTREAM_429_BACKOFF_BASE,
    UPSTREAM_429_BACKOFF_CAP,
)


class _FakeResponse:
    def __init__(self, status_code: int, headers: dict = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False

    async def aclose(self):
        self.closed = True


async def _close_fn(resp):
    await resp.aclose()


def test_parse_retry_after_missing_uses_default():
    assert parse_retry_after(None, 1.0) == 1.0
    assert parse_retry_after("", 2.0) == 2.0


def test_parse_retry_after_delta_seconds():
    assert parse_retry_after("5", 1.0) == 5.0
    assert parse_retry_after("-3", 1.0) == -3.0


def test_parse_retry_after_http_date():
    from datetime import datetime, timezone, timedelta
    future = (datetime.now(timezone.utc) + timedelta(seconds=7)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    assert abs(parse_retry_after(future, 1.0) - 7.0) < 1.5


def test_parse_retry_after_garbage_falls_back():
    assert parse_retry_after("not-a-date", 4.0) == 4.0
    assert parse_retry_after("999999", 1.0) == UPSTREAM_429_BACKOFF_CAP


async def test_retries_until_success():
    state = {"n": 0}

    async def factory():
        state["n"] += 1
        if state["n"] <= 2:
            return _FakeResponse(429)
        return _FakeResponse(200)

    resp = await request_with_429_backoff(
        factory, max_retries=3, close_fn=_close_fn
    )
    assert resp.status_code == 200
    assert state["n"] == 3  # 2 retries + 1 success


async def test_retries_honors_retry_after(monkeypatch):
    delays = []
    state = {"n": 0}

    async def factory():
        state["n"] += 1
        return _FakeResponse(429, {"retry-after": "1"})

    async def spy_sleep(d):
        delays.append(d)

    monkeypatch.setattr("api.anthropic_adapters.asyncio.sleep", spy_sleep)

    resp = await request_with_429_backoff(
        factory, max_retries=2, close_fn=_close_fn
    )
    assert resp.status_code == 429
    # 3 calls total (initial + 2 retries); Retry-After=1 → both delays == 1
    assert state["n"] == 3
    assert delays == [1.0, 1.0]


async def test_retries_default_exponential_backoff(monkeypatch):
    delays = []
    state = {"n": 0}

    async def factory():
        state["n"] += 1
        return _FakeResponse(429)

    async def spy_sleep(d):
        delays.append(d)

    monkeypatch.setattr("api.anthropic_adapters.asyncio.sleep", spy_sleep)

    resp = await request_with_429_backoff(
        factory, max_retries=3, close_fn=_close_fn
    )
    assert resp.status_code == 429
    # default backoff: 1.0, 2.0, 4.0 (but capped at CAP=30)
    assert delays == [1.0, 2.0, 4.0]


async def test_exhausted_retries_returns_final_429():
    state = {"n": 0}

    async def factory():
        state["n"] += 1
        return _FakeResponse(429)

    resp = await request_with_429_backoff(
        factory, max_retries=2, close_fn=_close_fn
    )
    assert resp.status_code == 429
    assert state["n"] == 3  # initial + 2 retries
    # The final (returned) response must be closed by the caller, not the helper
    assert resp.closed is False


async def test_network_error_not_retried():
    state = {"n": 0}

    async def factory():
        state["n"] += 1
        if state["n"] == 1:
            raise ConnectionError("boom")
        return _FakeResponse(200)

    with pytest.raises(ConnectionError):
        await request_with_429_backoff(factory, max_retries=3, close_fn=_close_fn)
    # factory is only called once — the network error propagates immediately
    assert state["n"] == 1
