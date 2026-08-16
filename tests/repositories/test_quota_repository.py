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


def test_account_quotas_per_key_isolation(database, db_connection):
    """Global (account_quotas) quota is tracked per key, not per supplier.

    Mirrors the per-model window fix: with N keys the supplier-level daily quota
    must be counted independently for each key, so one key exhausting its
    upstream quota does not consume another key's budget.
    """
    repo = QuotaRepository(database)

    # Distinct quota per key
    repo.update_quota("acc", 500, 1000, key_id=0)
    repo.update_quota("acc", 200, 1000, key_id=1)

    k0 = repo.get_account_info("acc", key_id=0)
    k1 = repo.get_account_info("acc", key_id=1)
    assert k0["quota_remaining"] == 500
    assert k1["quota_remaining"] == 200

    # Aggregated (no key_id) sums across keys
    agg = repo.get_account_info("acc")
    assert agg["quota_remaining"] == 700
    assert agg["quota_limit"] == 2000

    # Unavailable is per key
    repo.mark_model_unavailable("acc", "m1", key_id=0)
    assert "m1" in repo.get_account_info("acc", key_id=0)["unavailable_models"]
    assert "m1" not in repo.get_account_info("acc", key_id=1)["unavailable_models"]

    batch = repo.get_unavailable_models_batch(["acc"])
    assert batch.get(("acc", 0)) == {"m1"}
    assert batch.get(("acc", 1)) == set()

    # Usage accumulates per key
    repo.record_usage("acc", 10, 20, "m1", key_id=0)
    repo.record_usage("acc", 5, 5, "m1", key_id=1)
    agg2 = repo.get_account_info("acc")
    assert agg2["total_input_tokens"] == 15
    assert agg2["total_output_tokens"] == 25


def test_reset_unavailable_models_single_key(database, db_connection):
    """reset_unavailable_models(key_id=...) only clears that key."""
    repo = QuotaRepository(database)
    repo.mark_model_unavailable("acc", "m1", key_id=0)
    repo.mark_model_unavailable("acc", "m2", key_id=1)

    repo.reset_unavailable_models("acc", key_id=0)
    assert "m1" not in repo.get_account_info("acc", key_id=0)["unavailable_models"]
    assert "m2" in repo.get_account_info("acc", key_id=1)["unavailable_models"]


def test_unavailable_models_by_account_union(database, db_connection):
    """The legacy LB helper unions unavailable across keys per supplier."""
    repo = QuotaRepository(database)
    repo.mark_model_unavailable("acc", "m1", key_id=0)
    repo.mark_model_unavailable("acc", "m2", key_id=1)

    by_account = repo.get_unavailable_models_by_account(["acc"])
    assert by_account.get("acc") == {"m1", "m2"}
