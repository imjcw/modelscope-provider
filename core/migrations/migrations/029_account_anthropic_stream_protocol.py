"""Migration 029: add anthropic_stream_protocol to accounts.

Some dual-protocol suppliers serve Anthropic-shaped ``/v1/messages`` but with a
**broken streaming path**: the response comes back ``200`` +
``content-type: text/event-stream`` + ``transfer-encoding: chunked`` and then
EOFs with a zero-byte body. Anthropic clients see that as
"streaming response ended before any complete data" and re-send the request
non-streaming, so every request is billed twice. SenseTime / 商汤 does exactly
this for its DeepSeek models, while the same account's OpenAI endpoint
(``/v1/chat/completions``) streams the very same models correctly.

We add a nullable ``anthropic_stream_protocol`` column (default ``"auto"``) so
the gateway can choose the upstream protocol per supplier when calling its
Anthropic endpoint, instead of always forcing ``/v1/messages``.

- ``"native"`` → current behaviour, hit ``/v1/messages`` unchanged.
- ``"openai"`` → convert the request to OpenAI format, hit
  ``/v1/chat/completions``, and convert the response (and SSE events) back to
  Anthropic format.
- ``"auto"``   → start native, and remember a switch to ``"openai"`` for a
  specific model once its stream comes back empty repeatedly.

Idempotent: no-op if the column already exists.
"""

import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register


@register
class AccountAnthropicStreamProtocol(Migration):
    version = 29
    description = (
        "Add anthropic_stream_protocol to accounts (per-supplier upstream "
        "protocol for Anthropic requests: native/openai/auto)"
    )

    def up(self, conn: sqlite3.Connection) -> None:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)")}
        if "anthropic_stream_protocol" in cols:
            return  # already applied (idempotent)
        conn.execute(
            "ALTER TABLE accounts ADD COLUMN anthropic_stream_protocol TEXT "
            "DEFAULT 'auto'"
        )
