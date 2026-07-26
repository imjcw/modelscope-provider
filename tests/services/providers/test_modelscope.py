"""Tests for the ModelScope rate-limit strategy."""

import pytest
from unittest.mock import Mock, patch

from provider.services.providers.modelscope import ModelScopeStrategy


@pytest.fixture
def mock_quota_updater():
    return Mock()


@pytest.fixture
def mock_quota_repo():
    return Mock()


@pytest.fixture
def strategy(mock_quota_updater, mock_quota_repo):
    return ModelScopeStrategy(
        quota_updater=mock_quota_updater,
        quota_repository=mock_quota_repo,
    )


class TestCheckRateLimit:
    def test_always_true(self, strategy):
        """ModelScope check_rate_limit should always return True."""
        assert strategy.check_rate_limit("acc1", "model-a") is True
        assert strategy.check_rate_limit("acc2", "model-b") is True


class TestRecordRequest:
    def test_delegates_to_updater(self, strategy, mock_quota_updater):
        """record_request should delegate to quota_updater.update_quota_after_request."""
        headers = {"modelscope-ratelimit-requests-remaining": "50"}
        strategy.record_request("acc1", "model-a", headers, 200)

        mock_quota_updater.update_quota_after_request.assert_called_once()
        call_args = mock_quota_updater.update_quota_after_request.call_args
        account = call_args[0][0]
        assert account.account_id == "acc1"
        assert call_args[0][1] == headers
        assert call_args[0][2] == "model-a"


class TestRecordUsage:
    def test_delegates_to_updater(self, strategy, mock_quota_updater):
        """record_usage should delegate to quota_updater.update_quota_from_usage."""
        strategy.record_usage("acc1", "model-a", 100, 200)

        mock_quota_updater.update_quota_from_usage.assert_called_once()
        call_args = mock_quota_updater.update_quota_from_usage.call_args
        account = call_args[0][0]
        assert account.account_id == "acc1"
        assert call_args[0][1] == 100
        assert call_args[0][2] == 200


class TestGetQuotaInfo:
    def test_returns_repo_data(self, strategy, mock_quota_repo):
        """get_quota_info should return data from quota_repository."""
        mock_quota_repo.get_account_info.return_value = {
            "quota_remaining": 42,
            "quota_limit": 100,
        }
        info = strategy.get_quota_info("acc1")
        assert info == {"quota_remaining": 42, "quota_limit": 100}

    def test_returns_zeros_when_no_data(self, strategy, mock_quota_repo):
        """get_quota_info should return zeros when repo returns None."""
        mock_quota_repo.get_account_info.return_value = None
        info = strategy.get_quota_info("acc1")
        assert info == {"quota_remaining": 0, "quota_limit": 0}
