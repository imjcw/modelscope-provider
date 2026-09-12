"""Tests for AccountRepository.count_active_keys (multi-key quota multiplier).

``count_active_keys`` feeds the quota multiplier: an account with N active
keys holds N× the per-key sliding-window limit. It must count only active
``account_api_keys`` rows and fall back to 1 (the primary key) when none
exist.
"""
import pytest

from provider.repositories.account_repository import AccountRepository


@pytest.fixture
def repo(database):
    return AccountRepository(database)


def test_no_extra_keys_returns_one(repo):
    """An account with only its primary key counts as 1."""
    acc = repo.create(name="Single", api_keys=["k1"], base_url="http://x")
    assert repo.count_active_keys(acc["account_id"]) == 1


def test_counts_active_keys(repo):
    """Extra active keys increase the count."""
    acc = repo.create(name="Multi", api_keys=["k1"], base_url="http://x")
    repo.add_api_key(acc["id"], "k2")
    repo.add_api_key(acc["id"], "k3")
    assert repo.count_active_keys(acc["account_id"]) == 3


def test_frozen_keys_not_counted(repo):
    """Frozen keys are excluded from the multiplier."""
    acc = repo.create(name="Frozen", api_keys=["k1"], base_url="http://x")
    k2 = repo.add_api_key(acc["id"], "k2")
    repo.update_api_key_status(k2["id"], "frozen")
    assert repo.count_active_keys(acc["account_id"]) == 1


def test_unknown_account_returns_one(repo):
    """A non-existent account falls back to 1 (primary-key semantics)."""
    assert repo.count_active_keys("no-such-account") == 1


def test_accounts_isolated(repo):
    """Key counts are per-account, not global."""
    a = repo.create(name="A", api_keys=["ka"], base_url="http://x")
    b = repo.create(name="B", api_keys=["kb"], base_url="http://x")
    repo.add_api_key(a["id"], "ka2")
    assert repo.count_active_keys(a["account_id"]) == 2
    assert repo.count_active_keys(b["account_id"]) == 1


def test_delete_api_key_returns_whether_deleted(repo):
    """delete_api_key reports whether a row was actually removed.

    The admin endpoint relies on this to distinguish success from 404.
    """
    acc = repo.create(name="Del", api_keys=["k1"], base_url="http://x")
    k2 = repo.add_api_key(acc["id"], "k2")
    assert repo.delete_api_key(k2["id"]) is True
    assert repo.delete_api_key(k2["id"]) is False
    assert repo.delete_api_key(999999) is False


def test_api_key_id_to_logical_maps_sort_order(repo):
    """account_api_keys.id maps to the 0-based logical index used in logs/quotas."""
    acc = repo.create(name="Map", api_keys=["k1"], base_url="http://x")
    k2 = repo.add_api_key(acc["id"], "k2")
    k3 = repo.add_api_key(acc["id"], "k3")
    assert repo.api_key_id_to_logical(k2["id"]) == 1
    assert repo.api_key_id_to_logical(k3["id"]) == 2
    assert repo.api_key_id_to_logical(999999) == 0
