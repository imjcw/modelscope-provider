"""Tests for the in-memory cache layer (ConfigCache + RateLimitCache)."""
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.cache import ConfigCache, RateLimitCache, RateLimitWindow


def _mock_db():
    """Create a mock DatabaseManager with a working context manager chain."""
    db = Mock()
    conn_mock = MagicMock()  # MagicMock supports __enter__ / __exit__
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
    """RateLimitWindow tracks the per-window state."""

    def test_is_expired_when_window_elapsed(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5,
                            window_start=time.time() - 20, request_count=3)
        assert w.is_expired is True

    def test_not_expired_within_window(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5,
                            window_start=time.time() - 5, request_count=3)
        assert w.is_expired is False

    def test_is_exhausted_when_at_limit(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5,
                            window_start=time.time(), request_count=5)
        assert w.is_exhausted is True

    def test_not_exhausted_below_limit(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5,
                            window_start=time.time(), request_count=3)
        assert w.is_exhausted is False

    def test_reset_clears_count(self):
        w = RateLimitWindow("a", "m", window_seconds=10, max_requests=5,
                            window_start=time.time() - 20, request_count=5)
        w.reset()
        assert w.request_count == 0
        assert w.is_expired is False


class TestRateLimitCacheCheck:
    """RateLimitCache.check() — the core hot-path method."""

    def test_first_request_creates_window_and_allows(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        assert cache.check("acc-1", "model-1", 3600, 100) is True
        assert ("acc-1", "model-1") in cache._dirty

    def test_second_request_counts_within_window(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "model-1", 3600, 100)
        assert cache.check("acc-1", "model-1", 3600, 100) is True
        w = cache._windows[("acc-1", "model-1")]
        assert w.request_count == 2

    def test_quota_exhausted_returns_false(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        # Exhaust the quota of 3
        assert cache.check("acc-1", "m1", 3600, 3) is True
        assert cache.check("acc-1", "m1", 3600, 3) is True
        assert cache.check("acc-1", "m1", 3600, 3) is True
        assert cache.check("acc-1", "m1", 3600, 3) is False

    def test_expired_window_resets(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        # Create a window, then manually expire it
        cache.check("acc-1", "m1", 1, 100)  # 1-second window
        w = cache._windows[("acc-1", "m1")]
        w.window_start = time.time() - 10  # expired
        # Should reset and allow
        assert cache.check("acc-1", "m1", 1, 100) is True
        assert w.request_count == 1  # reset to 1 (counts the new request)

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

    def test_existing_window_returns_remaining(self):
        db = _mock_db()
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        cache = RateLimitCache(db)
        cache.check("acc-1", "m1", 3600, 100)
        cache.check("acc-1", "m1", 3600, 100)  # 2 requests used
        info = cache.get_quota_info("acc-1", "m1")
        assert info["quota_remaining"] == 98
        assert info["quota_limit"] == 100


class TestRateLimitCacheLoadAll:
    """RateLimitCache loads existing windows from the database on init."""

    def test_load_all_from_db(self):
        db = _mock_db()
        fake_rows = [
            {"account_id": "acc-1", "model_name": "m1",
             "window_start": "2026-07-26T10:00:00", "request_count": 5},
            {"account_id": "acc-2", "model_name": "m2",
             "window_start": "2026-07-26T10:00:00", "request_count": 3},
        ]
        db.get_connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = fake_rows
        cache = RateLimitCache(db)
        assert len(cache._windows) == 2
        assert cache._windows[("acc-1", "m1")].request_count == 5
        assert cache._windows[("acc-2", "m2")].request_count == 3