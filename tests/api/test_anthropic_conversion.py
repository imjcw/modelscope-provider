"""Unit tests for the Anthropic ↔ OpenAI conversion layer.

The conversion path (``anthropic_stream_protocol='openai'``, or the ``auto``
empty-stream switch) re-shapes requests, responses and SSE streams between the
two protocols. These tests pin the behaviours real clients depend on:

- the Anthropic close sequence (``message_delta``/``message_stop``) must carry
  the upstream usage even when OpenAI streams it in a separate chunk AFTER the
  finish chunk (``stream_options.include_usage``);
- parallel tool-call argument fragments must land on their own block, not on
  whichever block was opened last;
- image blocks must survive the Anthropic → OpenAI request conversion;
- stop-reason / tool-choice mappings must produce valid enum values.
"""
import asyncio
import json

from fastapi.testclient import TestClient

from provider.api.anthropic_adapters import openai_finish_to_anthropic_stop
from provider.api.anthropic_routes import (
    AnthropicMessagesRequest,
    _anthropic_to_openai_body,
    stream_response_anthropic,
)
from provider.api.openai_routes import (
    ChatCompletionRequest,
    _build_request_body,
    _openai_message_to_anthropic,
)
from provider.main import create_app
from provider.models.account import build_ms_account
from provider.services.alias_router import RoutingResult


# ── SSE converter fakes ───────────────────────────────────────────────────

def _sse(chunk):
    return "data: " + json.dumps(chunk)


class _FakeStream:
    """Just enough of an httpx streaming response for the SSE converter."""

    def __init__(self, lines):
        self._lines = list(lines)

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def _collect_events(lines):
    """Run the converter and return ``{"event": type, "data": dict}`` items.

    ``message_delta`` / ``message_stop`` carry no ``type`` inside their data —
    the type lives on the ``event:`` line — so both sources are considered.
    """

    async def run():
        return [ev async for ev in stream_response_anthropic(_FakeStream(lines), "test-model")]

    events = []
    for raw in asyncio.run(run()):
        event_type = None
        data = None
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    data = None
        if isinstance(data, dict):
            events.append({"event": event_type or data.get("type"), "data": data})
    return events


# ── usage reporting across upstream conventions ───────────────────────────

def test_message_delta_carries_usage_from_trailing_chunk():
    """OpenAI streams usage AFTER the finish chunk (include_usage); the
    Anthropic close sequence must be deferred until it can carry the totals."""
    lines = [
        _sse({"choices": [{"index": 0, "delta": {"role": "assistant", "content": "He"},
                           "finish_reason": None}]}),
        _sse({"choices": [{"index": 0, "delta": {"content": "llo"}, "finish_reason": None}]}),
        _sse({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}),
        _sse({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 50,
                                       "prompt_tokens_details": {"cached_tokens": 80}}}),
        "data: [DONE]",
    ]
    events = _collect_events(lines)

    delta = next(e["data"] for e in events if e["event"] == "message_delta")
    assert delta["usage"]["output_tokens"] == 50
    assert delta["usage"]["input_tokens"] == 100
    assert delta["usage"]["cache_read_input_tokens"] == 80
    # close sequence must be the tail of the stream
    assert events[-1]["event"] == "message_stop"
    assert events[-2]["event"] == "message_delta"


def test_usage_inside_finish_chunk_still_works():
    """Upstreams that put usage IN the finish chunk (DeepSeek-style) keep
    working and report it immediately."""
    lines = [
        _sse({"choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": None}]}),
        _sse({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
              "usage": {"prompt_tokens": 100, "completion_tokens": 50}}),
        "data: [DONE]",
    ]
    events = _collect_events(lines)

    delta = next(e["data"] for e in events if e["event"] == "message_delta")
    assert delta["usage"]["output_tokens"] == 50
    assert delta["usage"]["input_tokens"] == 100


def test_close_sequence_flushed_when_stream_ends_without_done():
    """An upstream that closes after finish without [DONE]/usage must still
    produce a complete message_delta + message_stop tail."""
    lines = [
        _sse({"choices": [{"delta": {"content": "hi"}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
    ]
    events = _collect_events(lines)
    assert events[-2]["event"] == "message_delta"
    assert events[-1]["event"] == "message_stop"


# ── parallel tool calls ───────────────────────────────────────────────────

def test_parallel_tool_call_fragments_land_on_their_own_blocks():
    """Argument fragments of interleaved parallel calls must go to the block
    of THEIR call — not to whichever block was opened last."""
    lines = [
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "call_A", "type": "function",
             "function": {"name": "fa", "arguments": ""}}]}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 1, "id": "call_B", "type": "function",
             "function": {"name": "fb", "arguments": ""}}]}, "finish_reason": None}]}),
        # Fragments for call A arrive after B was opened, carrying only the
        # streaming index (no id) — the common OpenAI fragment shape.
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '{"a":'}},
            {"index": 0, "function": {"arguments": "1}"}}]}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 1, "function": {"arguments": '{"b":2}'}}]}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        "data: [DONE]",
    ]
    events = _collect_events(lines)

    starts = [(e["data"]["index"], e["data"]["content_block"]["name"])
              for e in events if e["event"] == "content_block_start"]
    assert starts == [(0, "fa"), (1, "fb")]

    deltas = [(e["data"]["index"], e["data"]["delta"]["partial_json"])
              for e in events if e["event"] == "content_block_delta"]
    assert deltas == [(0, '{"a":'), (0, "1}"), (1, '{"b":2}')]


def test_sequential_tool_call_fragments_unchanged():
    """The common sequential shape (all fragments of call A, then call B)
    must keep mapping 1:1 onto Anthropic blocks."""
    lines = [
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "call_A", "type": "function",
             "function": {"name": "fa", "arguments": '{"x":1}'}}]}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 1, "id": "call_B", "type": "function",
             "function": {"name": "fb", "arguments": '{"y":2}'}}]}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        "data: [DONE]",
    ]
    events = _collect_events(lines)
    deltas = [(e["data"]["index"], e["data"]["delta"]["partial_json"])
              for e in events if e["event"] == "content_block_delta"]
    assert deltas == [(0, '{"x":1}'), (1, '{"y":2}')]


def test_name_repeat_with_index_only_does_not_open_duplicate_block():
    """Some upstreams repeat ``name`` on every fragment without the id; the
    dedupe must still recognise the call via its streaming index, or the
    client receives a second tool_use block that never receives input."""
    lines = [
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "call_A", "type": "function",
             "function": {"name": "fa", "arguments": ""}}]}, "finish_reason": None}]}),
        # Repeat with name but no id — must not open a second block.
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"name": "fa", "arguments": '{"x":'}}]},
            "finish_reason": None}]}),
        _sse({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": "1}"}}]}, "finish_reason": None}]}),
        _sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        "data: [DONE]",
    ]
    events = _collect_events(lines)

    starts = [e for e in events if e["event"] == "content_block_start"]
    assert len(starts) == 1, "name-repeat must not open a second tool_use block"
    deltas = [(e["data"]["index"], e["data"]["delta"]["partial_json"])
              for e in events if e["event"] == "content_block_delta"]
    assert deltas == [(0, '{"x":'), (0, "1}")]


# ── request conversion ────────────────────────────────────────────────────

def test_image_blocks_convert_to_openai_vision_parts():
    """Anthropic image blocks must reach the OpenAI upstream as image_url
    parts (base64 → data: URL) instead of being silently dropped."""
    data = AnthropicMessagesRequest(model="m", max_tokens=100, messages=[
        {"role": "user", "content": [
            {"type": "image",
             "source": {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="}},
            {"type": "text", "text": "what is this?"},
        ]},
    ])
    body = asyncio.run(_anthropic_to_openai_body(data, "m"))
    content = body["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "image_url",
                          "image_url": {"url": "data:image/png;base64,aGVsbG8="}}
    assert content[1] == {"type": "text", "text": "what is this?"}


def test_url_sourced_images_pass_through_as_image_url():
    data = AnthropicMessagesRequest(model="m", max_tokens=100, messages=[
        {"role": "user", "content": [
            {"type": "image", "source": {"type": "url", "url": "https://x.test/i.png"}},
        ]},
    ])
    body = asyncio.run(_anthropic_to_openai_body(data, "m"))
    assert body["messages"][0]["content"] == [
        {"type": "image_url", "image_url": {"url": "https://x.test/i.png"}},
    ]


def test_text_only_content_stays_a_string():
    """Text-only blocks keep the plain-string shape most upstreams expect."""
    data = AnthropicMessagesRequest(model="m", max_tokens=100, messages=[
        {"role": "user", "content": [{"type": "text", "text": "hi"}]},
    ])
    body = asyncio.run(_anthropic_to_openai_body(data, "m"))
    assert body["messages"][0]["content"] == "hi"


def test_tool_choice_none_dict_form_is_forwarded():
    data = AnthropicMessagesRequest(
        model="m", max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"name": "t", "input_schema": {"type": "object"}}],
        tool_choice={"type": "none"},
    )
    body = asyncio.run(_anthropic_to_openai_body(data, "m"))
    assert body["tool_choice"] == "none"


def test_openai_data_url_image_maps_to_anthropic_base64_source():
    """OpenAI base64 images become Anthropic base64 sources — a data: URI in a
    url source would be rejected by real Anthropic upstreams."""
    msg = {"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
        {"type": "text", "text": "look"},
    ]}
    anthro = _openai_message_to_anthropic(msg)
    assert anthro["content"][0] == {"type": "image", "source": {
        "type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}


# ── mappings & field passthrough ──────────────────────────────────────────

def test_content_filter_maps_to_a_valid_anthropic_stop_reason():
    """Anthropic's stop_reason enum has no ``stopped_by``; the closest
    semantic for OpenAI's content_filter is ``refusal``."""
    assert openai_finish_to_anthropic_stop("content_filter") == "refusal"
    assert openai_finish_to_anthropic_stop("stop") == "end_turn"
    assert openai_finish_to_anthropic_stop("length") == "max_tokens"
    assert openai_finish_to_anthropic_stop("tool_calls") == "tool_use"


def test_max_completion_tokens_and_reasoning_effort_are_forwarded():
    """Newer OpenAI clients send these instead of / besides max_tokens; the
    rebuilt upstream body must not silently drop them."""
    data = ChatCompletionRequest(
        model="alias", messages=[{"role": "user", "content": "hi"}],
        max_completion_tokens=2048, reasoning_effort="low",
    )
    body = asyncio.run(_build_request_body(data, "actual-model"))
    assert body["max_completion_tokens"] == 2048
    assert body["reasoning_effort"] == "low"


# ── end-to-end: the conversion entry requests include_usage ──────────────

MESSAGES_URL = "https://up.test/v1/messages"
CHAT_URL = "https://up.test/v1/chat/completions"

OPENAI_STREAM_LINES = [
    _sse({"choices": [{"index": 0, "delta": {"role": "assistant", "content": "hi"},
                       "finish_reason": None}]}),
    _sse({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}),
    _sse({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}),
    "data: [DONE]",
]


class _HttpResponse:
    """Just enough of an httpx.Response for the Anthropic routes."""

    def __init__(self, lines=None, text="", headers=None):
        self.status_code = 200
        self.text = text
        self.headers = headers or {"content-type": "text/event-stream"}
        self._lines = list(lines or [])

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aclose(self):
        return None


class _FakeHttpClient:
    def __init__(self, response):
        self.calls = []
        self._response = response

    async def request(self, account, method, url, json=None, stream=False,
                      key_string="", auth_style="bearer"):
        self.calls.append({"url": url, "auth_style": auth_style,
                           "stream": stream, "body": dict(json or {})})
        return self._response

    async def close_all_clients(self):
        return None


class _FakeRouter:
    def __init__(self, account):
        self._account = account

    def get_candidates(self, alias):
        return [RoutingResult(account=self._account, model_name=alias,
                              key_id=1, key_string="sk-test")]

    def acquire(self, *a, **k):
        return None

    def release(self, *a, **k):
        return None


def _account(stream_protocol):
    return build_ms_account(
        {
            "account_id": "acc-conv",
            "name": "up",
            "base_url": "https://up.test/v1",
            "anthropic_base_url": "https://up.test",
            "anthropic_auth_style": "bearer",
            "anthropic_stream_protocol": stream_protocol,
            "provider_type": "sensetime",
        },
        api_key_records=[{"api_key": "sk-test", "status": "active"}],
    )


def _client_message_deltas(sse_text):
    deltas = []
    event_type = None
    for line in sse_text.splitlines():
        line = line.strip()
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:") and event_type == "message_delta":
            deltas.append(json.loads(line[5:]))
    return deltas


def test_conversion_stream_requests_include_usage_and_reports_totals():
    """Streaming through the OpenAI endpoint must ask for the trailing usage
    chunk, and the client's message_delta must carry its real totals."""
    http = _FakeHttpClient(_HttpResponse(lines=OPENAI_STREAM_LINES))
    app = create_app()
    with TestClient(app) as client:
        client.app.state.services["http_client"] = http
        client.app.state.services["alias_router"] = _FakeRouter(_account("openai"))
        resp = client.post("/anthropic/v1/messages", json={
            "model": "deepseek-v4-pro", "max_tokens": 64,
            "messages": [{"role": "user", "content": "hi"}], "stream": True,
        })
        assert resp.status_code == 200, resp.text

    assert http.calls[0]["url"] == CHAT_URL
    assert http.calls[0]["body"]["stream"] is True
    assert http.calls[0]["body"]["stream_options"] == {"include_usage": True}

    deltas = _client_message_deltas(resp.text)
    assert deltas and deltas[-1]["usage"]["output_tokens"] == 5
    assert deltas[-1]["usage"]["input_tokens"] == 10


def test_native_stream_does_not_request_openai_options():
    """The native Anthropic upstream must not receive OpenAI-only fields."""
    http = _FakeHttpClient(_HttpResponse(lines=[
        'data: {"type":"message_start","message":{"id":"msg_1","type":"message",'
        '"role":"assistant","content":null,"model":"m","stop_reason":null,'
        '"stop_sequence":null,"usage":{"input_tokens":1,"output_tokens":1}}}\n\n',
        'data: {"type":"message_stop"}\n\n',
    ]))
    app = create_app()
    with TestClient(app) as client:
        client.app.state.services["http_client"] = http
        client.app.state.services["alias_router"] = _FakeRouter(_account("native"))
        resp = client.post("/anthropic/v1/messages", json={
            "model": "deepseek-v4-pro", "max_tokens": 64,
            "messages": [{"role": "user", "content": "hi"}], "stream": True,
        })
        assert resp.status_code == 200, resp.text

    assert http.calls[0]["url"] == MESSAGES_URL
    assert http.calls[0]["body"]["stream"] is True
    assert "stream_options" not in http.calls[0]["body"]
