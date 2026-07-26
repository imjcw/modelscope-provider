"""Tests for the PerModelFixedWindowStrategy per-model rate-limit strategy."""

import pytest
from datetime import datetime, timezone, timedelta

from provider.services.providers.per_model import PerModelFixedWindowStrategy


@pytest.fixture
def strategy(database):
    """Per-model strategy with small limits for fast testing."""
    return PerModelFixedWindowStrategy(
        db=database,
        window_seconds=10,
        max_requests=5,
        model_configs={
            "model-a": {"window_seconds": 10, "max_requests": 5},
            "model-b": {"window_seconds": 10, "max_requests": 3},
            "model-c": {"window_seconds": 5, "max_requests": 2},
        },
    )


class TestCheckRateLimit:
    def test_first_request_creates_window(self, strategy, database):
        """First request for a model should create a window row and return True."""
        assert strategy.check_rate_limit("acc1", "model-a") is True

        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT request_count FROM account_rate_windows "
                "WHERE account_id = ? AND model_name = ?",
                ("acc1", "model-a"),
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

    def test_models_have_independent_windows(self, strategy):
        """Different models under the same account should have independent windows."""
        # Exhaust model-a
        for _ in range(5):
            strategy.check_rate_limit("acc1", "model-a")
        assert strategy.check_rate_limit("acc1", "model-a") is False

        # model-b should still be fresh (different window)
        assert strategy.check_rate_limit("acc1", "model-b") is True

    def test_models_with_different_limits(self, strategy):
        """Models with different max_requests should enforce their own limits."""
        # model-b has max_requests=3
        assert strategy.check_rate_limit("acc1", "model-b") is True  # 1/3
        assert strategy.check_rate_limit("acc1", "model-b") is True  # 2/3
        assert strategy.check_rate_limit("acc1", "model-b") is True  # 3/3
        assert strategy.check_rate_limit("acc1", "model-b") is False  # blocked

        # model-a (max_requests=5) should still have 5 available
        for _ in range(5):
            assert strategy.check_rate_limit("acc1", "model-a") is True

    def test_window_reset(self, database):
        """An expired window should reset the counter."""
        strategy = PerModelFixedWindowStrategy(
            db=database,
            window_seconds=1,
            max_requests=2,
            model_configs={"m": {"window_seconds": 1, "max_requests": 2}},
        )

        assert strategy.check_rate_limit("acc1", "m") is True
        assert strategy.check_rate_limit("acc1", "m") is True
        assert strategy.check_rate_limit("acc1", "m") is False

        # Manually backdate the window_start to simulate expiry
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE account_rate_windows SET window_start = ? "
                "WHERE account_id = ? AND model_name = ?",
                (old_time, "acc1", "m"),
            )

        # Should be allowed again after window reset
        assert strategy.check_rate_limit("acc1", "m") is True

    def test_separate_accounts(self, strategy):
        """Different accounts should have independent windows."""
        for _ in range(5):
            strategy.check_rate_limit("acc1", "model-a")
        assert strategy.check_rate_limit("acc1", "model-a") is False
        # acc2 should still be fresh
        assert strategy.check_rate_limit("acc2", "model-a") is True

    def test_unconfigured_model_uses_defaults(self, database):
        """A model not in model_configs should use the default window/max_requests."""
        strategy = PerModelFixedWindowStrategy(
            db=database,
            window_seconds=10,
            max_requests=3,
            model_configs={},
        )
        for _ in range(3):
            assert strategy.check_rate_limit("acc1", "unknown-model") is True
        assert strategy.check_rate_limit("acc1", "unknown-model") is False

    def test_different_models_same_account_independent_windows(self, strategy):
        """Verify that model-a and model-b truly have separate counters."""
        # Use model-a 3 times
        strategy.check_rate_limit("acc1", "model-a")
        strategy.check_rate_limit("acc1", "model-a")
        strategy.check_rate_limit("acc1", "model-a")

        # model-b should still have all 3 requests available
        assert strategy.check_rate_limit("acc1", "model-b") is True
        assert strategy.check_rate_limit("acc1", "model-b") is True
        assert strategy.check_rate_limit("acc1", "model-b") is True
        # 4th should be blocked (max_requests=3 for model-b)
        assert strategy.check_rate_limit("acc1", "model-b") is False

        # model-a should have 2 remaining (3 used out of 5)
        assert strategy.check_rate_limit("acc1", "model-a") is True
        assert strategy.check_rate_limit("acc1", "model-a") is True
        assert strategy.check_rate_limit("acc1", "model-a") is False  # 6th → blocked


class TestRecordRequest:
    def test_noop(self, strategy):
        """record_request should be a no-op for per-model strategy."""
        strategy.check_rate_limit("acc1", "model-a")
        # Should not raise or change state
        strategy.record_request("acc1", "model-a", {}, 200)
        strategy.record_request("acc1", "model-a", {}, 500)


class TestGetQuotaInfo:
    def test_no_window_returns_default(self, strategy):
        """No window row should return the min remaining across all configured models."""
        info = strategy.get_quota_info("nonexistent")
        # model-c has max_requests=2, so min remaining is 2
        assert info["quota_remaining"] == 2
        # max limit across all models is 5 (model-a)
        assert info["quota_limit"] == 5

    def test_after_requests_aggregates(self, strategy):
        """After some requests, remaining should reflect min across models."""
        strategy.check_rate_limit("acc1", "model-a")  # 1/5
        strategy.check_rate_limit("acc1", "model-b")  # 1/3
        info = strategy.get_quota_info("acc1")
        # model-b has 2 remaining, model-a has 4 remaining → min is 2
        assert info["quota_remaining"] == 2
        assert info["quota_limit"] == 5  # max limit across all models

    def test_expired_window_shows_full(self, database):
        """An expired window should show full quota."""
        strategy = PerModelFixedWindowStrategy(
            db=database,
            window_seconds=1,
            max_requests=5,
            model_configs={"m": {"window_seconds": 1, "max_requests": 5}},
        )
        strategy.check_rate_limit("acc1", "m")

        old_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE account_rate_windows SET window_start = ? "
                "WHERE account_id = ? AND model_name = ?",
                (old_time, "acc1", "m"),
            )

        info = strategy.get_quota_info("acc1")
        assert info["quota_remaining"] == 5


class TestGetModelQuotaInfo:
    def test_no_window(self, strategy):
        """No window row should return full quota for the model."""
        info = strategy.get_model_quota_info("acc1", "model-a")
        assert info["quota_remaining"] == 5
        assert info["quota_limit"] == 5

    def test_after_requests(self, strategy):
        """After some requests, remaining should decrease."""
        strategy.check_rate_limit("acc1", "model-a")
        strategy.check_rate_limit("acc1", "model-a")
        info = strategy.get_model_quota_info("acc1", "model-a")
        assert info["quota_remaining"] == 3
        assert info["quota_limit"] == 5

    def test_different_models_have_different_limits(self, strategy):
        """get_model_quota_info should return the correct limit per model."""
        info_a = strategy.get_model_quota_info("acc1", "model-a")
        assert info_a["quota_limit"] == 5
        info_b = strategy.get_model_quota_info("acc1", "model-b")
        assert info_b["quota_limit"] == 3

    def test_expired_window_shows_full(self, database):
        """An expired window should show full quota."""
        strategy = PerModelFixedWindowStrategy(
            db=database,
            window_seconds=1,
            max_requests=5,
            model_configs={"m": {"window_seconds": 1, "max_requests": 5}},
        )
        strategy.check_rate_limit("acc1", "m")

        old_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE account_rate_windows SET window_start = ? "
                "WHERE account_id = ? AND model_name = ?",
                (old_time, "acc1", "m"),
            )

        info = strategy.get_model_quota_info("acc1", "m")
        assert info["quota_remaining"] == 5