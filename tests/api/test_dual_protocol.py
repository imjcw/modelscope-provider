"""Tests for dual-protocol (OpenAI + Anthropic) upstream URL selection.

A single supplier may expose OpenAI and Anthropic endpoints at DIFFERENT URLs,
so it carries ``base_url`` (OpenAI) and an optional ``anthropic_base_url``
(Anthropic). The gateway must pick the right upstream URL + auth style based on
the client's entry point:

* ``/openai/v1/chat/completions`` → speak OpenAI at ``base_url`` (Bearer auth).
* ``/anthropic/v1/messages``        → speak Anthropic at ``anthropic_base_url``
  (falling back to ``base_url``), with ``x-api-key`` auth.

These tests use the real app via TestClient and stub the downstream HTTP client
+ alias router so no real network or DB seeding of mappings is required.
"""

import json

from fastapi.testclient import TestClient

from provider.main import create_app
from models.account import build_ms_account
from services.alias_router import RoutingResult


OPENAI_JSON = json.dumps({
    "id": "chatcmpl-1", "object": "chat.completion",
    "choices": [{"index": 0,
                 "message": {"role": "assistant", "content": "hi"},
                 "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
})

ANTHROPIC_JSON = json.dumps({
    "id": "msg_1", "type": "message", "role": "assistant",
    "content": [{"type": "text", "text": "hi"}],
    "model": "claude-x", "stop_reason": "end_turn", "stop_sequence": None,
    "usage": {"input_tokens": 0, "output_tokens": 0},
})


class FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200
        self.headers = {}

    async def aclose(self):
        return None


class FakeHttpClient:
    """Captures every upstream request's (url, auth_style)."""

    def __init__(self, captured):
        self._captured = captured

    async def request(self, account, method, url, json=None, stream=False,
                      key_string="", auth_style="bearer"):
        self._captured.append((url, auth_style))
        text = ANTHROPIC_JSON if "v1/messages" in url else OPENAI_JSON
        return FakeResponse(text)

    async def close_all_clients(self):
        return None


class FakeRouter:
    """Returns a single candidate backed by a configured dual-protocol account."""

    def __init__(self, account):
        self._account = account

    def get_candidates(self, alias):
        return [RoutingResult(
            account=self._account, model_name="test-model",
            key_id=1, key_string="sk-test",
        )]

    def acquire(self, *a, **k):
        return None

    def release(self, *a, **k):
        return None

    def record_usage(self, *a, **k):
        return None


def _make_dual_account():
    return build_ms_account(
        {
            "account_id": "acc-1",
            "name": "dual",
            "base_url": "https://openai.example.com/v1",
            "anthropic_base_url": "https://anthropic.example.com",
            "provider_type": "anthropic",
        },
        api_key_records=[{"api_key": "sk-test", "status": "active"}],
    )


def test_openai_entry_uses_base_url_bearer():
    """/openai entry should hit base_url with OpenAI format + Bearer auth."""
    captured = []
    account = _make_dual_account()
    app = create_app()
    with TestClient(app) as client:
        client.app.state.services["http_client"] = FakeHttpClient(captured)
        client.app.state.services["alias_router"] = FakeRouter(account)
        resp = client.post(
            "/openai/v1/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200, resp.text
        assert ("https://openai.example.com/v1/chat/completions", "bearer") in captured


def test_anthropic_entry_uses_anthropic_base_url_x_api_key():
    """/anthropic entry should hit anthropic_base_url with x-api-key auth."""
    captured = []
    account = _make_dual_account()
    app = create_app()
    with TestClient(app) as client:
        client.app.state.services["http_client"] = FakeHttpClient(captured)
        client.app.state.services["alias_router"] = FakeRouter(account)
        resp = client.post(
            "/anthropic/v1/messages",
            json={"model": "test", "max_tokens": 100,
                  "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200, resp.text
        assert ("https://anthropic.example.com/v1/messages", "anthropic") in captured


def test_anthropic_entry_falls_back_to_base_url():
    """When anthropic_base_url is empty, the Anthropic entry falls back to base_url."""
    captured = []
    account = build_ms_account(
        {
            "account_id": "acc-2",
            "name": "no-anthropic-url",
            "base_url": "https://only.example.com",
            "anthropic_base_url": "",
            "provider_type": "anthropic",
        },
        api_key_records=[{"api_key": "sk-test", "status": "active"}],
    )
    app = create_app()
    with TestClient(app) as client:
        client.app.state.services["http_client"] = FakeHttpClient(captured)
        client.app.state.services["alias_router"] = FakeRouter(account)
        resp = client.post(
            "/anthropic/v1/messages",
            json={"model": "test", "max_tokens": 100,
                  "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200, resp.text
        # base_url has no trailing slash stripping issue: "https://only.example.com/v1/messages"
        assert ("https://only.example.com/v1/messages", "anthropic") in captured


def test_protocol_independent_of_provider_type():
    """Protocol is chosen by the client's entry point, NOT by provider_type.

    A supplier with ``provider_type='modelscope'`` (NOT 'anthropic') that still
    exposes an Anthropic endpoint via ``anthropic_base_url`` must be reached with
    the Anthropic protocol when the client calls ``/anthropic/...``. This proves
    ``provider_type`` is the supplier's *type*, not its protocol.
    """
    captured = []
    # provider_type is deliberately NOT 'anthropic' here.
    account = build_ms_account(
        {
            "account_id": "acc-3",
            "name": "dual-non-anthropic-type",
            "base_url": "https://openai.example.com/v1",
            "anthropic_base_url": "https://anthropic.example.com",
            "provider_type": "modelscope",
        },
        api_key_records=[{"api_key": "sk-test", "status": "active"}],
    )
    app = create_app()
    with TestClient(app) as client:
        client.app.state.services["http_client"] = FakeHttpClient(captured)
        client.app.state.services["alias_router"] = FakeRouter(account)

        # /openai → OpenAI protocol at base_url
        r1 = client.post(
            "/openai/v1/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r1.status_code == 200, r1.text
        assert ("https://openai.example.com/v1/chat/completions", "bearer") in captured

        # /anthropic → Anthropic protocol at anthropic_base_url, even though
        # provider_type is 'modelscope'
        r2 = client.post(
            "/anthropic/v1/messages",
            json={"model": "test", "max_tokens": 100,
                  "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r2.status_code == 200, r2.text
        assert ("https://anthropic.example.com/v1/messages", "anthropic") in captured
