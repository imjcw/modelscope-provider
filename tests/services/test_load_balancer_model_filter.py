import pytest
from provider.models.account import ModelScopeAccount
from provider.services.load_balancer import LoadBalancer


def _make_accounts():
    return [
        ModelScopeAccount(
            account_id="acc1", api_key="k1", base_url="https://u1/v1",
            name="supplier1",
        ),
        ModelScopeAccount(
            account_id="acc2", api_key="k2", base_url="https://u2/v1",
            name="supplier2",
        ),
    ]


def test_select_without_model_repo_round_robin():
    """Without model repo, behaves as before — round-robin over all accounts."""
    accounts = _make_accounts()
    lb = LoadBalancer(accounts)

    a1 = lb.select_account("qwen-max")
    assert a1.account_id == "acc1"
    a2 = lb.select_account("qwen-max")
    assert a2.account_id == "acc2"
    a3 = lb.select_account("qwen-max")
    assert a3.account_id == "acc1"  # wraps around


class MockSupplierModelRepo:
    """Mock repo that returns suppliers for a model by account_id."""

    def __init__(self, model_to_accounts):
        self.model_to_accounts = model_to_accounts

    def find_suppliers_for_model(self, model_name):
        account_ids = self.model_to_accounts.get(model_name, [])
        return [{"account_id": aid} for aid in account_ids]


def test_select_filters_by_model():
    """Only returns suppliers that declare the model."""
    accounts = _make_accounts()
    repo = MockSupplierModelRepo({
        "qwen-max": ["acc1"],   # only acc1 supports qwen-max
    })
    lb = LoadBalancer(accounts, supplier_model_repo=repo)

    result = lb.select_account("qwen-max")
    assert result.account_id == "acc1"


def test_select_fallback_when_no_supplier_declares_model():
    """Falls back to all accounts when no supplier declares the model."""
    accounts = _make_accounts()
    repo = MockSupplierModelRepo({})  # nothing declared
    lb = LoadBalancer(accounts, supplier_model_repo=repo)

    result = lb.select_account("nonexistent-model")
    # Should fall back to round-robin over all accounts
    assert result.account_id in ("acc1", "acc2")


def test_select_unavailable_models_still_filtered():
    """Even with model repo, unavailable_models filter still applies."""
    accounts = _make_accounts()
    accounts[0].unavailable_models = {"qwen-max"}  # acc1 unavailable for qwen-max
    repo = MockSupplierModelRepo({
        "qwen-max": ["acc1", "acc2"],   # both suppliers declare qwen-max
    })
    lb = LoadBalancer(accounts, supplier_model_repo=repo)

    # Both suppliers declare qwen-max, so model filter keeps both candidates.
    # The unavailable_models filter then excludes acc1, leaving only acc2.
    result = lb.select_account("qwen-max")
    assert result.account_id == "acc2"


def test_no_accounts_raises():
    lb = LoadBalancer([])
    with pytest.raises(ValueError, match="No accounts available"):
        lb.select_account("qwen-max")
