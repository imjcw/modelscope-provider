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
        1000,
        key_id=0,
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

    mock_repo.update_quota.assert_called_once_with("test_account", 0, 1000, key_id=0)
    mock_repo.mark_model_unavailable.assert_called_once_with("test_account", "hy3", key_id=0)


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
    """Missing rate-limit headers should NOT zero out quota (skip update).

    Upstreams that don't return ratelimit headers keep their last-known quota
    values instead of being reset to 0/0 (which made the dashboard falsely
    report "quota exhausted").
    """
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)

    account = Mock()
    account.account_id = "test_account"

    headers = {}  # No rate limit headers

    updater.update_quota_after_request(account, headers, "hy3")

    mock_repo.update_quota.assert_not_called()


def test_custom_header_names():
    """Custom header names from header_config should be honored."""
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)
    account = Mock()
    account.account_id = "acct"
    header_config = {
        "supplier_total": "x-total",
        "supplier_remaining": "x-remaining",
        "model_total": "x-model-total",
        "model_remaining": "x-model-remaining",
    }
    headers = {
        "x-total": "500",
        "x-remaining": "50",
        "x-model-total": "200",
        "x-model-remaining": "10",
    }
    updater.update_quota_after_request(account, headers, "hy3", header_config)
    mock_repo.update_quota.assert_called_once_with("acct", 50, 500, key_id=0)
    mock_repo.update_model_quota.assert_called_once_with("acct", "hy3", 10, 200, key_id=0)


def test_used_header_derives_remaining():
    """A *_used header should derive remaining = total - used."""
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)
    account = Mock()
    account.account_id = "acct"
    header_config = {
        "supplier_total": "x-total",
        "supplier_used": "x-used",
    }
    headers = {"x-total": "500", "x-used": "120"}
    updater.update_quota_after_request(account, headers, "hy3", header_config)
    # remaining = 500 - 120 = 380
    mock_repo.update_quota.assert_called_once_with("acct", 380, 500, key_id=0)


def test_invalid_used_header_skips_update():
    """An unparseable *_used header should skip the quota update."""
    mock_repo = Mock()
    updater = QuotaUpdater(mock_repo)
    account = Mock()
    account.account_id = "acct"
    header_config = {
        "supplier_total": "x-total",
        "supplier_used": "x-used",
    }
    headers = {"x-total": "bad", "x-used": "not-a-number"}
    updater.update_quota_after_request(account, headers, "hy3", header_config)
    mock_repo.update_quota.assert_not_called()
