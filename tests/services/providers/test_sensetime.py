"""Tests for the SenseTime fixed-window rate-limit strategy."""

import pytest
from datetime import datetime, timezone, timedelta

from provider.services.providers.sensetime import SenseTimeStrategy


@pytest.fixture
def strategy(database):
    """SenseTime strategy with small limits for fast testing."""
    return SenseTimeStrategy(db=database, window_seconds=10, max_requests=5)


class TestCheckRateLimit:
    def test_first_request_creates_window(self, strategy, database):
        """First request should create a window row and return True."""
        assert strategy.check_rate_limit("acc1", "model-a") is True

        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT request_count FROM account_rate_windows WHERE account_id = ? AND model_name = ?",
                ("acc1", "__global__"),
            ).fetchone()
        assert row is not None
        assert row["request_count"] == 1

    def test_increments_within_window(self, strategy):
        """Subsequent requests within the window should increment the counter."""
        for i in range(5):
            assert strategy.check_rate_limit("acc1", "model-a") is True

    def test_blocks_at_limit(self, strategy):
        """Request at max_requests should pass; the next one should be blocked."""
        for _ in range(5):
            assert strategy.check_rate_limit("acc1", "model-a") is True
        # 6th request should be blocked
        assert strategy.check_rate_limit("acc1", "model-a") is False

    def test_window_reset(self, database):
        """An expired window should reset the counter."""
        strategy = SenseTimeStrategy(db=database, window_seconds=1, max_requests=2)

        assert strategy.check_rate_limit("acc1", "m") is True
        assert strategy.check_rate_limit("acc1", "m") is True
        assert strategy.check_rate_limit("acc1", "m") is False

        # Manually backdate the window_start to simulate expiry
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE account_rate_windows SET window_start = ? WHERE account_id = ? AND model_name = ?",
                (old_time, "acc1", "__global__"),
            )

        # Should be allowed again after window reset
        assert strategy.check_rate_limit("acc1", "m") is True

    def test_separate_accounts(self, strategy):
        """Different accounts should have independent windows."""
        for _ in range(5):
            strategy.check_rate_limit("acc1", "m")
        assert strategy.check_rate_limit("acc1", "m") is False
        # acc2 should still be fresh
        assert strategy.check_rate_limit("acc2", "m") is True

    def test_key_count_scales_limit(self, database):
        """key_count multiplies the effective quota (N keys → N× budget)."""
        strategy = SenseTimeStrategy(db=database, window_seconds=10, max_requests=3)

        # Single key: blocked at 4th request (limit 3)
        for _ in range(3):
            assert strategy.check_rate_limit("acc1", "m") is True
        assert strategy.check_rate_limit("acc1", "m") is False

        # Backdate the window past expiry (window_seconds=10) so it resets,
        # then use key_count=2 → limit 6
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE account_rate_windows SET window_start = ? WHERE account_id = ? AND model_name = ?",
                (old_time, "acc1", "__global__"),
            )
        for _ in range(6):
            assert strategy.check_rate_limit("acc1", "m", key_count=2) is True
        assert strategy.check_rate_limit("acc1", "m", key_count=2) is False

    def test_key_count_default_is_one(self, strategy):
        """Omitting key_count keeps the original per-key limit."""
        for _ in range(5):
            assert strategy.check_rate_limit("acc1", "m") is True
        assert strategy.check_rate_limit("acc1", "m") is False


class TestRecordRequest:
    def test_noop(self, strategy):
        """record_request should be a no-op for SenseTime."""
        strategy.check_rate_limit("acc1", "m")
        # Should not raise or change state
        strategy.record_request("acc1", "m", {}, 200)
        strategy.record_request("acc1", "m", {}, 500)


class TestGetQuotaInfo:
    def test_no_window(self, strategy):
        """No window row should return full quota."""
        info = strategy.get_quota_info("nonexistent")
        assert info["quota_remaining"] == 5
        assert info["quota_limit"] == 5

    def test_after_requests(self, strategy):
        """After some requests, remaining should decrease."""
        strategy.check_rate_limit("acc1", "m")
        strategy.check_rate_limit("acc1", "m")
        info = strategy.get_quota_info("acc1")
        assert info["quota_remaining"] == 3
        assert info["quota_limit"] == 5

    def test_expired_window_shows_full(self, database):
        """An expired window should show full quota."""
        strategy = SenseTimeStrategy(db=database, window_seconds=1, max_requests=5)
        strategy.check_rate_limit("acc1", "m")

        old_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE account_rate_windows SET window_start = ? WHERE account_id = ? AND model_name = ?",
                (old_time, "acc1", "__global__"),
            )

        info = strategy.get_quota_info("acc1")
        assert info["quota_remaining"] == 5
