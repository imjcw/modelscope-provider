"""Tests for the per-supplier Anthropic upstream protocol
(``accounts.anthropic_stream_protocol``: native / openai / auto).

Some suppliers (e.g. SenseTime / 商汤) serve an Anthropic-shaped
``/v1/messages`` whose *streaming* path answers ``200`` +
``content-type: text/event-stream`` and then EOFs with a zero-byte body.
Anthropic clients read that as "streaming response ended before any complete
data", retry the whole request non-streaming, and the request gets billed
twice. These tests cover the escape hatch that routes such a supplier through
its (working) OpenAI endpoint instead, and the ``auto`` mode that switches on
its own without any configuration.
"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from provider.api import anthropic_routes as stream_routes
from provider.api.anthropic_routes import (
    EMPTY_STREAM_LIMIT,
    reset_stream_protocol_overrides,
)
from provider.main import create_app
from provider.models.account import build_ms_account
from provider.services.alias_router import RoutingResult

# The app loads the routes as ``provider.api.anthropic_routes``, so the module
# object we poke at must be that one — a bare ``api.anthropic_routes`` import
# would bind a second copy with its own (always-empty) switch memory.
_overrides = stream_routes._stream_protocol_overrides
_counts = stream_routes._empty_stream_counts


ENDPOINT = "/anthropic/v1/messages"
MESSAGES_URL = "https://up.test/v1/messages"
CHAT_URL = "https://up.test/v1/chat/completions"

REQUEST_BODY = {
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 64,
    "system": [{"type": "text", "text": "be brief"}],
    "tools": [{"name": "fn", "description": "d", "input_schema": {"type": "object"}}],
}


# ── Fakes ─────────────────────────────────────────────────────────────────

SSE_LINE = (
    'data: {"type":"message_start","message":{"id":"msg_1","type":"message",'
    '"role":"assistant","content":null,"model":"deepseek-v4-pro",'
    '"stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":1,'
    '"output_tokens":1}}}\n\n'
)
DONE_LINE = 'data: {"type":"message_stop"}\n\n'


class _HttpResponse:
    """Just enough of an httpx.Response for the Anthropic routes."""

    def __init__(self, lines=None, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"content-type": "text/event-stream"}
        self._lines = list(lines or [])

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aclose(self):
        return None


def _empty_stream():
    """200 + text/event-stream that closes without a single SSE event."""
    return _HttpResponse(lines=[], headers={"content-type": "text/event-stream"})


def _ok_stream():
    return _HttpResponse(lines=[SSE_LINE, DONE_LINE])


def _openai_nonstream(prompt_tokens=89179, cache_read=88960, cache_creation=100):
    """OpenAI upstream usage, cache inside prompt_tokens (the OpenAI rule)."""
    usage = {"prompt_tokens": prompt_tokens, "completion_tokens": 7}
    if cache_read or cache_creation:
        usage["prompt_tokens_details"] = {
            "cached_tokens": cache_read,
            "prompt_partial_cached_tokens": cache_creation,
        }
    return _HttpResponse(
        lines=[],
        text=json.dumps({
            "id": "chatcmpl-1",
            "choices": [{"message": {"role": "assistant", "content": "hi"},
                         "finish_reason": "stop"}],
            "usage": usage,
        }),
        headers={"content-type": "application/json"},
    )


def _anthropic_nonstream(input_tokens=305, cache_read=221952, cache_creation=0):
    """Anthropic upstream usage, DeepSeek convention: cache outside input_tokens."""
    usage = {"input_tokens": input_tokens, "output_tokens": 10}
    if cache_read:
        usage["cache_read_input_tokens"] = cache_read
    if cache_creation:
        usage["cache_creation_input_tokens"] = cache_creation
    return _HttpResponse(
        lines=[],
        text=json.dumps({
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "hi"}],
            "model": "deepseek-v4-pro",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": usage,
        }),
        headers={"content-type": "application/json"},
    )


def _quota_input_tokens(database, account_id):
    """Sum of total_input_tokens for the account today.

    The quota write runs off the request thread, so poll until it lands.
    """
    today = database.get_today_date()
    for _ in range(50):
        with database.get_connection() as conn:
            rows = conn.execute(
                "SELECT total_input_tokens FROM account_quotas "
                "WHERE account_id = ? AND quota_date = ?",
                (account_id, today),
            ).fetchall()
        total = sum(r["total_input_tokens"] or 0 for r in rows)
        if total:
            return total
        time.sleep(0.02)
    return 0


class _FakeHttpClient:
    """Replays configured responses and captures what was sent upstream."""

    def __init__(self, responses):
        self.calls = []
        self._responses = list(responses)

    async def request(self, account, method, url, json=None, stream=False,
                      key_string="", auth_style="bearer"):
        self.calls.append({
            "url": url,
            "auth_style": auth_style,
            "stream": stream,
            "body": dict(json or {}),
        })
        idx = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[idx]

    async def close_all_clients(self):
        return None


class _FakeRouter:
    """Single candidate, so the whole request path runs without a DB."""

    def __init__(self, account):
        self._account = account

    def get_candidates(self, alias):
        # The test DB has no alias mapping, so identity resolution applies:
        # the model the client asked for *is* the model the upstream gets.
        return [RoutingResult(
            account=self._account, model_name=alias,
            key_id=1, key_string="sk-test",
        )]

    def acquire(self, *a, **k):
        return None

    def release(self, *a, **k):
        return None


def _account(stream_protocol, provider_type="sensetime"):
    return build_ms_account(
        {
            "account_id": "acc-1",
            "name": "up",
            "base_url": "https://up.test/v1",
            "anthropic_base_url": "https://up.test",
            "anthropic_auth_style": "bearer",
            "anthropic_stream_protocol": stream_protocol,
            "provider_type": provider_type,
        },
        api_key_records=[{"api_key": "sk-test", "status": "active"}],
    )


@pytest.fixture(autouse=True)
def _clear_stream_memory():
    reset_stream_protocol_overrides()
    yield
    reset_stream_protocol_overrides()


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _post(client, http, account, stream=True):
    client.app.state.services["http_client"] = http
    client.app.state.services["alias_router"] = _FakeRouter(account)
    return client.post(ENDPOINT, json={**REQUEST_BODY, "stream": stream})


# ── native ────────────────────────────────────────────────────────────────

def test_native_mode_keeps_the_messages_endpoint(client):
    """Explicit 'native' keeps today's behaviour and the supplier's auth style."""
    http = _FakeHttpClient([_ok_stream()])
    resp = _post(client, http, _account("native"))
    assert resp.status_code == 200, resp.text
    call = http.calls[0]
    assert call["url"] == MESSAGES_URL
    assert call["auth_style"] == "bearer"
    assert call["body"]["model"] == "deepseek-v4-pro"
    assert call["body"]["stream"] is True
    # Anthropic shape is preserved untouched.
    assert call["body"]["system"] == [{"type": "text", "text": "be brief"}]
    assert "fn" == call["body"]["tools"][0]["name"]


# ── openai ────────────────────────────────────────────────────────────────

def test_openai_mode_converts_body_and_hits_chat_completions(client):
    """Explicit 'openai' converts to the OpenAI endpoint and auth scheme."""
    http = _FakeHttpClient([_ok_stream()])
    resp = _post(client, http, _account("openai"))
    assert resp.status_code == 200, resp.text
    call = http.calls[0]
    assert call["url"] == CHAT_URL
    assert call["auth_style"] == "bearer"

    body = call["body"]
    # The block-array system prompt becomes one text system message.
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
    assert "system" not in body
    # Tools are reshaped to the OpenAI function schema.
    assert body["tools"] == [{
        "type": "function",
        "function": {"name": "fn", "description": "d", "parameters": {"type": "object"}},
    }]
    # No Anthropic-only field leaks through.
    assert "thinking" not in body
    assert "stop_sequences" not in body


# ── auto ──────────────────────────────────────────────────────────────────

def test_auto_mode_switches_after_consecutive_empty_streams(client, caplog):
    """'auto' stays native until a model's stream comes back empty repeatedly."""
    http = _FakeHttpClient([_empty_stream(), _empty_stream(), _ok_stream()])
    account = _account("auto")

    for _ in range(3):
        resp = _post(client, http, account)
        assert resp.status_code == 200, resp.text

    urls = [c["url"] for c in http.calls]
    assert urls == [MESSAGES_URL, MESSAGES_URL, CHAT_URL]
    assert _overrides[("acc-1", "deepseek-v4-pro")] == "openai"
    assert any(
        "empty streams" in r.message for r in caplog.records
    ), "switch must be announced in the log so the operator can find it"


def test_auto_mode_recounts_after_a_successful_stream(client):
    """A good stream resets the empty-streak, so it takes two *fresh* empties
    to switch again instead of remembering the old one."""
    http = _FakeHttpClient(
        [_empty_stream(), _ok_stream(), _empty_stream(), _empty_stream(), _ok_stream()]
    )
    account = _account("auto")

    for _ in range(5):
        resp = _post(client, http, account)
        assert resp.status_code == 200, resp.text

    # The second empty (request 2) cleared the first streak, so requests 3-4 are
    # still native and the switch only fires after the 4th request finishes.
    assert [c["url"] for c in http.calls] == [MESSAGES_URL] * 4 + [CHAT_URL]
    assert _overrides[("acc-1", "deepseek-v4-pro")] == "openai"
    # The 5th request streamed fine, so the empty counter is back to zero.
    assert _counts.get(("acc-1", "deepseek-v4-pro")) is None


def test_auto_mode_never_switches_without_an_openai_endpoint(client):
    """A pure-Anthropic supplier has no /chat/completions to fall back onto."""
    http = _FakeHttpClient([_empty_stream() for _ in range(EMPTY_STREAM_LIMIT + 2)])
    account = _account("auto", provider_type="anthropic")

    for _ in range(EMPTY_STREAM_LIMIT + 2):
        resp = _post(client, http, account)
        assert resp.status_code == 200, resp.text

    assert [c["url"] for c in http.calls] == [MESSAGES_URL] * (EMPTY_STREAM_LIMIT + 2)
    assert "openai" not in _overrides.get(
        ("acc-1", "deepseek-v4-pro"), "")


def test_auto_mode_is_per_model(client):
    """A switch learned on one model must not leak onto another."""
    other = dict(REQUEST_BODY, model="sensenova-6.8-flash-lite")
    http = _FakeHttpClient([_empty_stream() for _ in range(EMPTY_STREAM_LIMIT + 1)])
    account = _account("auto")

    for _ in range(EMPTY_STREAM_LIMIT):
        _post(client, http, account)
    assert http.calls[-1]["url"] == MESSAGES_URL

    resp = client.post(
        ENDPOINT,
        json={**other, "stream": True},
    )
    assert resp.status_code == 200, resp.text
    assert http.calls[-1]["url"] == MESSAGES_URL
    assert _overrides.get(
        ("acc-1", "sensenova-6.8-flash-lite")) is None


# ── empty-stream observability ────────────────────────────────────────────

def test_empty_stream_is_not_logged_as_a_clean_200(client):
    """An empty upstream stream must be visible in the logs, not look healthy."""
    http = _FakeHttpClient([_empty_stream()])
    _post(client, http, _account("native"))

    admin = client.app.state.admin_service
    logs, _ = admin.log_repo.find_all()
    empty = [r for r in logs
             if r["actual_model_id"] == "deepseek-v4-pro" and r["is_stream"]]
    assert empty, "the streaming attempt must be logged at all"
    row = empty[-1]
    assert row["status_code"] == -1
    assert row["error_source"] == "upstream"
    assert row["error_message"]


# ── default / persistence ─────────────────────────────────────────────────

def test_stream_protocol_defaults_to_auto(database):
    """Migration 029 must default existing and new accounts to 'auto'."""
    from provider.repositories.account_repository import AccountRepository

    repo = AccountRepository(database)
    created = repo.create(
        name="up",
        base_url="https://up.test/v1",
        api_keys=["sk-test"],
        provider_type="sensetime",
    )
    assert created["anthropic_stream_protocol"] == "auto"

    with database.get_connection() as conn:
        conn.execute("UPDATE accounts SET anthropic_stream_protocol = 'openai'")
        conn.commit()
    assert repo.find_by_id(created["id"])["anthropic_stream_protocol"] == "openai"

    # Typos fall back to the default instead of being stored and silently ignored.
    updated = repo.update(created["id"], anthropic_stream_protocol="opnai")
    assert updated["anthropic_stream_protocol"] == "auto"


# ── non-streaming ─────────────────────────────────────────────────────────
# The non-streaming branch is where the cache convention used to go wrong: it is
# the only Anthropic path whose usage never passes through the streaming parsers,
# and it is exactly the path a client falls back onto when it retries a failed
# stream — which is how the empty-stream bug shows up in practice.


def test_nonstream_openai_mode_counts_cache_tokens(client):
    """'openai' mode with stream=false must not lose the cache portion.

    The upstream usage is converted to Anthropic shape before logging, which
    renames the cache onto ``cache_read_input_tokens`` — a key the extractor
    used not to read, so every non-stream request in 'openai' mode was logged
    with cached_tokens = 0.
    """
    http = _FakeHttpClient([_openai_nonstream()])
    resp = _post(client, http, _account("openai"), stream=False)
    assert resp.status_code == 200, resp.text
    call = http.calls[0]
    assert call["url"] == CHAT_URL
    assert call["stream"] is False

    # The converted response still carries the cache for the client.
    assert resp.json()["usage"]["cache_read_input_tokens"] == 88960

    logs, _ = client.app.state.admin_service.log_repo.find_all()
    row = next(r for r in logs
               if r["actual_model_id"] == "deepseek-v4-pro" and not r["is_stream"])
    assert row["cached_tokens"] == 88960
    # The cache sits inside prompt_tokens here, so input_tokens is untouched.
    assert row["input_tokens"] == 89179


def test_nonstream_native_mode_folds_cache_into_quota(client, database):
    """The cache-outside convention must be folded before the quota write.

    log_request normalises for the log row, but the quota update ran on the raw
    numbers — 305 instead of 222257 for a 222k prompt.
    """
    http = _FakeHttpClient([_anthropic_nonstream()])
    resp = _post(client, http, _account("native"), stream=False)
    assert resp.status_code == 200, resp.text
    assert http.calls[0]["url"] == MESSAGES_URL

    logs, _ = client.app.state.admin_service.log_repo.find_all()
    row = next(r for r in logs
               if r["actual_model_id"] == "deepseek-v4-pro" and not r["is_stream"])
    assert (row["input_tokens"], row["cached_tokens"]) == (305 + 221952, 221952)

    assert _quota_input_tokens(database, "acc-1") == 305 + 221952


def test_manual_native_mode_never_claims_it_switched(client, caplog):
    """A supplier pinned to 'native' must not populate the auto-switch memory.

    _effective_stream_protocol ignores that memory for manual modes, so writing
    to it and logging a switch that never happened would send an operator
    looking in the wrong place during an outage.
    """
    http = _FakeHttpClient([_empty_stream() for _ in range(EMPTY_STREAM_LIMIT + 1)])
    account = _account("native")

    for _ in range(EMPTY_STREAM_LIMIT + 1):
        _post(client, http, account)

    assert not _overrides, "manual modes must not populate the switch memory"
    assert not _counts, "manual modes must not keep counting empties either"
    assert not any("empty streams" in r.message for r in caplog.records)
