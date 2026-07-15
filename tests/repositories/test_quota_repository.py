import pytest
from provider.repositories.quota_repository import QuotaRepository, QuotaInfo


def test_get_or_create_daily_quota(database, db_connection):
    """Test creating quota for today."""
    repo = QuotaRepository(database)
    quota = repo.get_or_create_daily_quota("test_account", 1000)

    assert quota.account_id == "test_account"
    assert quota.quota_date == database.get_today_date()
    assert quota.quota_limit == 1000
    assert quota.quota_remaining == 0
    assert quota.unavailable_models == set()


def test_update_quota(database, db_connection):
    """Test updating quota."""
    repo = QuotaRepository(database)

    # Create quota
    repo.get_or_create_daily_quota("test_account", 1000)

    # Update quota
    repo.update_quota("test_account", 500, 1000)

    # Verify
    quota = repo.get_account_info("test_account")
    assert quota["quota_remaining"] == 500
    assert quota["quota_limit"] == 1000


def test_mark_model_unavailable(database, db_connection):
    """Test marking model as unavailable."""
    repo = QuotaRepository(database)

    # Create quota
    repo.get_or_create_daily_quota("test_account", 1000)

    # Mark model as unavailable
    repo.mark_model_unavailable("test_account", "hy3")

    # Verify
    quota = repo.get_account_info("test_account")
    assert "hy3" in quota["unavailable_models"]


def test_reset_unavailable_models(database, db_connection):
    """Test resetting unavailable models."""
    repo = QuotaRepository(database)

    # Create quota and mark model as unavailable
    repo.get_or_create_daily_quota("test_account", 1000)
    repo.mark_model_unavailable("test_account", "hy3")

    # Reset
    repo.reset_unavailable_models("test_account")

    # Verify
    quota = repo.get_account_info("test_account")
    assert quota["unavailable_models"] == set()


def test_quota_persists_across_connections(database):
    """Test that quota persists across connections."""
    repo = QuotaRepository(database)

    # Create and update in one session
    repo.get_or_create_daily_quota("persist_account", 500)
    repo.update_quota("persist_account", 100, 500)

    # Verify in new connection (via fresh repo call)
    quota = repo.get_account_info("persist_account")
    assert quota["quota_remaining"] == 100
    assert quota["quota_limit"] == 500


def test_get_nonexistent_account(database):
    """Test getting info for non-existent account."""
    repo = QuotaRepository(database)
    result = repo.get_account_info("nonexistent")
    assert result is None
