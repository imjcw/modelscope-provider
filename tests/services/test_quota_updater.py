import pytest
from unittest.mock import Mock
from provider.services.quota_updater import QuotaUpdater


def test_update_quota_after_request():
    """Test quota update after successful request."""
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)

    account = Mock()
    account.account_id = "test_account"

    headers = {
        "modelscope-ratelimit-requests-remaining": "100",
        "modelscope-ratelimit-requests-limit": "1000"
    }

    updater.update_quota_after_request(account, headers, "hy3")

    mock_repo.update_quota.assert_called_once_with(
        "test_account",
        100,
        1000
    )


def test_mark_unavailable_when_quota_exhausted():
    """Test marking model as unavailable when quota is exhausted."""
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)

    account = Mock()
    account.account_id = "test_account"

    headers = {
        "modelscope-ratelimit-requests-remaining": "0",
        "modelscope-ratelimit-requests-limit": "1000"
    }

    updater.update_quota_after_request(account, headers, "hy3")

    mock_repo.update_quota.assert_called_once_with("test_account", 0, 1000)
    mock_repo.mark_model_unavailable.assert_called_once_with("test_account", "hy3")


def test_get_quota_info():
    """Test getting quota information."""
    mock_repo = Mock()
    mock_repo.get_account_info.return_value = {
        "account_id": "test_account",
        "quota_remaining": 100,
        "quota_limit": 1000,
        "unavailable_models": set(),
        "quota_date": "2026-07-15"
    }

    updater = QuotaUpdater(mock_repo)

    result = updater.get_quota_info("test_account")

    assert result["account_id"] == "test_account"
    assert result["quota_remaining"] == 100
    mock_repo.get_account_info.assert_called_once_with("test_account")


def test_update_quota_with_invalid_headers():
    """Test quota update with invalid header values (gracefully handles errors)."""
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)

    account = Mock()
    account.account_id = "test_account"

    headers = {
        "modelscope-ratelimit-requests-remaining": "invalid",
        "modelscope-ratelimit-requests-limit": "1000"
    }

    # QuotaUpdater catches and logs the error but doesn't raise
    # Verify that update_quota is NOT called when headers are invalid
    updater.update_quota_after_request(account, headers, "hy3")

    mock_repo.update_quota.assert_not_called()


def test_update_quota_missing_headers():
    """Test quota update with missing headers (defaults to 0)."""
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)

    account = Mock()
    account.account_id = "test_account"

    headers = {}  # No rate limit headers

    updater.update_quota_after_request(account, headers, "hy3")

    mock_repo.update_quota.assert_called_once_with(
        "test_account",
        0,  # quota_remaining defaults to 0
        0   # quota_limit defaults to 0
    )
