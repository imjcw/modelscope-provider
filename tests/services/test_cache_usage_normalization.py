"""Tests for cache-usage normalization across upstream conventions.

DeepSeek's Anthropic-compatible endpoint reports ``input_tokens`` as the
*uncached remainder* of the prompt (input=305 with cache_read=221952 for a
222k prompt), while OpenAI and the 商汤/智谱 Anthropic endpoints report it
inclusive. The gateway must fold the cache portion back in only for the
exclusive upstreams — otherwise the aggregated cache hit rate exceeds 100 %
(the miss volume goes negative) and token usage is under-counted.
"""
import uuid
from datetime import datetime, timedelta

import pytest

from provider.core.timezone import TZ
from provider.repositories.account_repository import AccountRepository
from provider.repositories.config_repository import ConfigRepository
from provider.repositories.log_repository import LogRepository
from provider.repositories.mapping_repository import MappingRepository
from provider.services.admin_service import AdminService
from provider.services.usage import normalize_cache_usage


@pytest.fixture(autouse=True)
def _clean_logs(database):
    """Isolate from rows leaked by other test modules (shared test DB file)."""
    with database.get_connection() as conn:
        conn.execute("DELETE FROM request_logs")
        conn.execute("DELETE FROM request_stats_minute")
    yield


def _make_service(db):
    return AdminService(
        AccountRepository(db), MappingRepository(db),
        ConfigRepository(db), LogRepository(db),
    )


def _run_030(db):
    """Apply migration 030's data repair straight onto the test database."""
    from provider.core.migrations import get_all_migrations

    migration = next(m for m in get_all_migrations() if m.version == 30)
    with db.get_connection() as conn:
        migration.up(conn)


class TestNormalizeCacheUsage:
    def test_inclusive_upstream_passes_through(self):
        # 商汤/智谱 Anthropic 端点与 OpenAI：缓存已算在 input 里，不能再加
        assert normalize_cache_usage(89179, 88960) == (89179, 88960, 0)
        assert normalize_cache_usage(66512, 65536) == (66512, 65536, 0)

    def test_exclusive_upstream_folds_cache_back_in(self):
        # DeepSeek：input 只是未命中部分，真实 prompt = input + cache_read
        assert normalize_cache_usage(305, 221952) == (222257, 221952, 0)
        assert normalize_cache_usage(4016, 16384) == (20400, 16384, 0)

    def test_creation_tokens_fold_when_reported_outside(self):
        assert normalize_cache_usage(10, 0, 400) == (410, 0, 400)

    def test_creation_tokens_do_not_double_count_when_inclusive(self):
        assert normalize_cache_usage(500, 200, 100) == (500, 200, 100)

    def test_zero_input_folds_full_cache(self):
        assert normalize_cache_usage(0, 50) == (50, 50, 0)

    def test_idempotent(self):
        once = normalize_cache_usage(305, 221952)
        assert normalize_cache_usage(*once) == once

    def test_none_and_zero_safe(self):
        assert normalize_cache_usage(0, 0) == (0, 0, 0)
        assert normalize_cache_usage(None, None) == (0, 0, 0)
        assert normalize_cache_usage(None, 50) == (50, 50, 0)


class TestLogRequestNormalizes:
    """log_request is the single write path for every route, so the guard lives there."""

    def _hour_ago(self):
        return (datetime.now(TZ) - timedelta(hours=1)).replace(
            microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

    def test_exclusive_upstream_row_is_normalized(self, database):
        svc = _make_service(database)
        svc.log_request(
            model="deepseekV4Flash", actual_model_id="deepseek-v4-flash",
            account_id="acc-1", status_code=200,
            input_tokens=305, output_tokens=10,
            cached_tokens=221952, prompt_partial_cached=0,
            request_start=self._hour_ago(), end_time=self._hour_ago(),
        )
        with database.get_connection() as conn:
            row = dict(conn.execute(
                "SELECT input_tokens, cached_tokens FROM request_logs"
            ).fetchone())
            stats = dict(conn.execute(
                "SELECT input_tokens, cached_tokens FROM request_stats_minute"
            ).fetchone())

        assert row["cached_tokens"] == 221952
        assert row["input_tokens"] == 305 + 221952
        # Stats table must never record cached > input.
        assert stats["cached_tokens"] <= stats["input_tokens"]
        assert stats["input_tokens"] == 305 + 221952

    def test_inclusive_upstream_row_is_untouched(self, database):
        svc = _make_service(database)
        svc.log_request(
            model="sense", actual_model_id="sensenova-6.8-flash-lite",
            account_id="acc-1", status_code=200,
            input_tokens=89179, output_tokens=100,
            cached_tokens=88960, prompt_partial_cached=0,
            request_start=self._hour_ago(), end_time=self._hour_ago(),
        )
        with database.get_connection() as conn:
            row = dict(conn.execute(
                "SELECT input_tokens, cached_tokens FROM request_logs"
            ).fetchone())

        assert row == {"input_tokens": 89179, "cached_tokens": 88960}


class TestStatsHitRate:
    """Mixed conventions in one window must not push the hit rate past 100 %."""

    def _hour_ago(self, minutes=0):
        return (datetime.now(TZ) - timedelta(minutes=60 + minutes)).replace(
            microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

    def _insert_minute(self, db, ts, input_tokens, cached_tokens):
        repo = LogRepository(db)
        repo.create(
            request_id=f"chit-{uuid.uuid4().hex[:12]}",
            model="deepseek-v4-flash", actual_model_id="deepseek-v4-flash",
            status_code=200, latency_ms=100,
            input_tokens=input_tokens, output_tokens=0,
        )
        repo.upsert_stats(
            timestamp=ts, model="deepseek-v4-flash",
            account_id="acc-1", client_key_name="",
            status_code=200, input_tokens=input_tokens,
            output_tokens=0, latency_ms=100, cached_tokens=cached_tokens,
        )

    def test_hit_rate_never_exceeds_100_with_exclusive_upstream_rows(self, database):
        # Rows shaped exactly like DeepSeek's Anthropic endpoint reports them:
        # cache reported outside input_tokens, as they were stored before the
        # write-path fix landed. Migration 030 is what repairs them.
        self._insert_minute(database, self._hour_ago(0), 305, 221952)
        self._insert_minute(database, self._hour_ago(1), 4016, 16384)

        svc = _make_service(database)
        assert svc.get_stats(days=30)["cache_hit_rate"] > 100.0  # 修复前的症状

        _run_030(database)
        out = svc.get_stats(days=30)

        assert out["cache_hit_rate"] <= 100.0
        # Both rows are ~100 % cache: 238336 of 242357 prompt tokens.
        assert out["cache_hit_rate"] == pytest.approx(
            238336 / (305 + 221952 + 4016 + 16384) * 100, abs=0.05)
        assert out["cached_tokens_total"] == 221952 + 16384
        # input_tokens reported inclusive, so it must include the cache portion.
        assert out["total_input_tokens"] == 305 + 221952 + 4016 + 16384

    def test_hit_rate_unchanged_for_inclusive_upstream_rows(self, database):
        self._insert_minute(database, self._hour_ago(0), 89179, 88960)
        self._insert_minute(database, self._hour_ago(1), 66512, 65536)

        svc = _make_service(database)
        out = svc.get_stats(days=30)

        total_input = 89179 + 66512
        total_cache = 88960 + 65536
        assert out["total_input_tokens"] == total_input
        assert out["cached_tokens_total"] == total_cache
        assert out["cache_hit_rate"] == pytest.approx(
            total_cache / total_input * 100, abs=0.05)

    def test_empty_window_is_zero(self, database):
        assert _make_service(database).get_stats(days=30)["cache_hit_rate"] == 0.0
