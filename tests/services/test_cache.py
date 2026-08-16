"""Tests for the in-memory cache layer (ConfigCache + RateLimitCache)."""
import json
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.cache import ConfigCache, RateLimitCache, RateLimitWindow


def _mock_db():
    """Create a mock DatabaseManager with a working context manager chain."""
    db = Mock()
    conn_mock = MagicMock()  # MagicMock supports __enter__ / __exit__
    conn_mock.__enter__.return_value = conn_mock  # `with` yields the same mock
    conn_mock.execute.return_value.fetchall.return_value = []
    db.get_connection.return_value = conn_mock
    return db


# ---------------------------------------------------------------------------
# ConfigCache
# ---------------------------------------------------------------------------


class TestConfigCache:
    """ConfigCache reads from ConfigRepository on init, then serves from memory."""

    def test_get_returns_cached_value(self):
        repo = Mock()
        repo.get_all.return_value = {
            "load_balancer_strategy": {"value": "round_robin", "description": "..."},
            "log_level": {"value": "INFO", "description": "..."},
        }
        cache = ConfigCache(repo)
        assert cache.get("load_balancer_strategy") == "round_robin"
        assert cache.get("log_level") == "INFO"

    def test_get_returns_none_for_missing_key(self):
        repo = Mock()
        repo.get_all.return_value = {}
        cache = ConfigCache(repo)
        assert cache.get("nonexistent") is None

    def test_set_updates_memory_then_db(self):
        repo = Mock()
        repo.get_all.return_value = {"key1": {"value": "old", "description": ""}}
        cache = ConfigCache(repo)
        cache.set("key1", "new")
        assert cache.get("key1") == "new"
        repo.set.assert_called_once_with("key1", "new")

    def test_reload_refreshes_from_db(self):
        repo = Mock()
        repo.get_all.return_value = {"k": {"value": "v1", "description": ""}}
        cache = ConfigCache(repo)
        assert cache.get("k") == "v1"

        # Simulate external change
        repo.get_all.return_value = {"k": {"value": "v2", "description": ""}}
        cache.reload()
        assert cache.get("k") == "v2"

    def test_get_all_returns_copy(self):
        repo = Mock()
        repo.get_all.return_value = {"a": {"value": "1", "description": ""}}
        cache = ConfigCache(repo)
        all_config = cache.get_all()
        assert all_config == {"a": "1"}
        # Modifying the returned dict should not affect the cache
        all_config["b"] = "2"
        assert cache.get("b") is None


# ---------------------------------------------------------------------------
# RateLimitCache
# ---------------------------------------------------------------------------


class TestRateLimitWindow:
    """RateLimitWindow tracks the per-sliding-window state."""

    def test_count_reflects_timestamps_within_window(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5)
        now = time.time()
        w.timestamps.append(now - 1)
        w.timestamps.append(now - 2)
        assert w.count == 2
        assert w.is_exhausted is False

    def test_purge_drops_old_timestamps(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5)
        now = time.time()
        w.timestamps.append(now - 100)  # outside 10s window
        w.timestamps.append(now - 1)    # inside
        assert w.count == 1
        # only the in-window timestamp remains
        assert len(w.timestamps) == 1

    def test_is_exhausted_when_at_limit(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5)
        now = time.time()
        for _ in range(5):
            w.timestamps.append(now)
        assert w.is_exhausted is True
        assert w.count == 5

    def test_not_exhausted_below_limit(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5)
        now = time.time()
        w.timestamps.append(now)
        assert w.is_exhausted is False

    def test_add_records_request_and_returns_count(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5)
        n = w.add()
        assert n == 1
        assert w.count == 1

    def test_window_start_is_now_minus_window_seconds(self):
        w = RateLimitWindow("a", "m", window_seconds=600, max_requests=5)
        # window_start should be ~600s before now
        assert abs((time.time() - w.window_start) - 600) < 2


class TestRateLimitCacheCheck:
    """RateLimitCache.check() — the core hot-path method."""

    def test_first_request_creates_window_and_allows(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        assert cache.check("acc-1", "model-1", 3600, 100) is True
        assert ("acc-1", "model-1", 0) in cache._dirty

    def test_second_request_counts_within_window(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "model-1", 3600, 100)
        assert cache.check("acc-1", "model-1", 3600, 100) is True
        w = cache._windows[("acc-1", "model-1", 0)]
        assert w.count == 2

    def test_quota_exhausted_returns_false(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        # Exhaust the quota of 3
        assert cache.check("acc-1", "m1", 3600, 3) is True
        assert cache.check("acc-1", "m1", 3600, 3) is True
        assert cache.check("acc-1", "m1", 3600, 3) is True
        assert cache.check("acc-1", "m1", 3600, 3) is False

    def test_stale_timestamps_are_purged(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=100)
        now = time.time()
        # A stale timestamp at the head, plus a recent one at the tail.
        w.timestamps.append(now - 100)  # outside the 10s window
        w.timestamps.append(now - 1)    # inside
        assert w.count == 1
        assert len(w.timestamps) == 1

    def test_check_allows_when_only_stale_timestamps_present(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 1, 100)
        w = cache._windows[("acc-1", "m1", 0)]
        # Replace the in-window timestamp with only a stale one at the front.
        w.timestamps.clear()
        w.timestamps.append(time.time() - 100)
        # The stale entry is purged on the next check; the new request is allowed.
        assert cache.check("acc-1", "m1", 1, 100) is True
        assert w.count == 1

    def test_different_accounts_independent(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        # Exhaust acc-1
        cache.check("acc-1", "m1", 3600, 1)
        assert cache.check("acc-1", "m1", 3600, 1) is False
        # acc-2 should still be allowed
        assert cache.check("acc-2", "m1", 3600, 1) is True

    def test_different_models_independent(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 3600, 1)
        assert cache.check("acc-1", "m1", 3600, 1) is False
        assert cache.check("acc-1", "m2", 3600, 1) is True

    def test_different_keys_independent(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        # Exhaust key 0
        cache.check("acc-1", "m1", 3600, 1, key_id=0)
        assert cache.check("acc-1", "m1", 3600, 1, key_id=0) is False
        # key 1 should still be allowed (per key+model isolation)
        assert cache.check("acc-1", "m1", 3600, 1, key_id=1) is True

    def test_get_model_count_across_keys_sums(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 3600, 100, key_id=0)
        cache.check("acc-1", "m1", 3600, 100, key_id=0)
        cache.check("acc-1", "m1", 3600, 100, key_id=1)
        info = cache.get_model_count_across_keys("acc-1", "m1", 3600, 100)
        assert info["request_count"] == 3
        # A model with no window returns None
        assert cache.get_model_count_across_keys("acc-1", "mX", 3600, 100) is None


class TestRateLimitCacheFlush:
    """RateLimitCache.flush() persists dirty windows to the database."""

    def test_flush_writes_dirty_windows(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 3600, 100)
        cache.check("acc-2", "m2", 3600, 100)

        flushed = cache.flush()
        assert flushed == 2
        # Dirty set should be cleared
        assert len(cache._dirty) == 0

    def test_flush_noop_when_nothing_dirty(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        assert cache.flush() == 0

    def test_flush_uses_upsert(self):
        db = _mock_db()
        # Get the connection mock that RateLimitCache will use at runtime
        conn_mock = db.get_connection.return_value.__enter__.return_value
        conn_mock.reset_mock()  # clear _load_all() calls from init
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 3600, 100)
        conn_mock.reset_mock()  # clear check() calls
        cache.flush()

        # Should have called execute with INSERT ... ON CONFLICT DO UPDATE
        calls = conn_mock.execute.call_args_list
        assert len(calls) >= 1
        sql = calls[0][0][0]
        assert "ON CONFLICT" in sql
        assert "account_rate_windows" in sql


class TestRateLimitCacheGetQuotaInfo:
    """RateLimitCache.get_quota_info() returns display info."""

    def test_no_window_returns_full_quota(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        info = cache.get_quota_info("acc-1", "m1")
        assert info["quota_remaining"] == 0  # No window, no max_requests known
        assert info["quota_limit"] == 0
        assert info["request_count"] is None  # no in-memory window -> fall back to DB

    def test_existing_window_returns_remaining(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 3600, 100)
        cache.check("acc-1", "m1", 3600, 100)  # 2 requests used
        info = cache.get_quota_info("acc-1", "m1")
        assert info["quota_remaining"] == 98
        assert info["quota_limit"] == 100

    def test_get_quota_info_specific_key(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 3600, 100, key_id=1)
        cache.check("acc-1", "m1", 3600, 100, key_id=1)  # 2 used on key 1
        info = cache.get_quota_info("acc-1", "m1", key_id=1)
        assert info["request_count"] == 2
        # key 0 has its own (empty) window
        info0 = cache.get_quota_info("acc-1", "m1", key_id=0)
        assert info0["request_count"] is None


class TestRateLimitCacheLoadAll:
    """RateLimitCache loads existing windows from the database on init."""

    def test_load_all_from_db(self):
        db = _mock_db()
        fake_rows = [
            {"account_id": "acc-1", "model_name": "m1", "key_id": 0,
             "window_start": "2026-07-26T10:00:00", "request_count": 5,
             "timestamps": json.dumps([time.time()] * 5)},
            {"account_id": "acc-2", "model_name": "m2", "key_id": 0,
             "window_start": "2026-07-26T10:00:00", "request_count": 3,
             "timestamps": json.dumps([time.time()] * 3)},
        ]
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = fake_rows
        cache = RateLimitCache(db)
        assert len(cache._windows) == 2
        assert cache._windows[("acc-1", "m1", 0)].count == 5
        assert cache._windows[("acc-2", "m2", 0)].count == 3