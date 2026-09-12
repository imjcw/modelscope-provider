"""Migration 030: fold cache tokens back into ``input_tokens``.

Upstream APIs disagree on whether ``input_tokens`` includes the cached portion
of the prompt:

- OpenAI (``prompt_tokens`` + ``prompt_tokens_details.cached_tokens``) and the
  Anthropic-compatible endpoints of 商汤/智谱 count the cache **inside**
  ``input_tokens`` — e.g. ``input_tokens=89179`` with
  ``cache_read_input_tokens=88960``.
- DeepSeek's Anthropic-compatible endpoint counts it **outside** — the returned
  ``input_tokens`` is only the uncached remainder, e.g. ``input_tokens=305``
  with ``cache_read_input_tokens=221952`` for a 222k prompt.

Both conventions were stored as-is, so the aggregated cache hit rate exceeded
100 % (the cached *miss* volume went negative) and DeepSeek token usage was
under-counted by roughly an order of magnitude in the quota tables.

This migrates historical rows into the single convention that
``services.usage.normalize_cache_usage`` now enforces at write time:
``input_tokens`` is always the full prompt size. Only rows where the cache is
reported outside ``input_tokens`` (``cached_tokens > input_tokens``) are
touched, so the already-inclusive upstreams are untouched. The condition is
therefore also what makes the migration idempotent — a second run matches
nothing.

``request_logs`` keeps cache *creation* in its own ``prompt_partial_cached``
column, so both counts are folded. ``request_stats_minute`` already folds
creation into ``cached_tokens`` at write time, so only that column is folded.

After folding, ``cached_tokens`` / ``prompt_partial_cached`` are *breakdowns*
of the new ``input_tokens`` (the new input already contains them), so they are
deliberately kept, not zeroed: the cache-hit-rate queries use them as the
numerator over ``input_tokens``. Never add them to ``input_tokens`` again.
"""

import sqlite3

from core.migrations.base import Migration
from core.migrations.registry import register


@register
class NormalizeCacheUsage(Migration):
    version = 30
    description = (
        "Fold cache tokens back into input_tokens for rows whose upstream "
        "reported the cache outside input_tokens"
    )

    def up(self, conn: sqlite3.Connection) -> None:
        # Guard each statement: a database migrated by an intermediate version
        # may lack a table the other statement needs (and the tests simulate
        # exactly that).
        cols = {
            name: {r[1] for r in conn.execute(f"PRAGMA table_info({name})")}
            for name in ("request_logs", "request_stats_minute")
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (name,),
            ).fetchone()
        }

        logs = cols.get("request_logs", set())
        if {"input_tokens", "cached_tokens"}.issubset(logs):
            creation = "prompt_partial_cached" if "prompt_partial_cached" in logs else 0
            conn.execute(
                f"UPDATE request_logs SET input_tokens = "
                f"input_tokens + cached_tokens + {creation} "
                f"WHERE cached_tokens + {creation} > input_tokens"
            )

        stats = cols.get("request_stats_minute", set())
        if {"input_tokens", "cached_tokens"}.issubset(stats):
            conn.execute(
                "UPDATE request_stats_minute SET input_tokens = "
                "input_tokens + cached_tokens "
                "WHERE cached_tokens > input_tokens"
            )
