import pytest
from provider.services.load_balancer import LoadBalancer


class MockAccount:
    """Mock account for testing."""
    def __init__(self, account_id: str, unavailable_models=None):
        self.account_id = account_id
        self.unavailable_models = unavailable_models or set()


def test_select_account_round_robin():
    """Test account selection with round-robin."""
    accounts = [
        MockAccount("account1"),
        MockAccount("account2"),
        MockAccount("account3")
    ]

    balancer = LoadBalancer(accounts)

    account1 = balancer.select_account()
    assert account1.account_id == "account1"

    account2 = balancer.select_account()
    assert account2.account_id == "account2"

    account3 = balancer.select_account()
    assert account3.account_id == "account3"


def test_select_account_skips_unavailable():
    """Test account selection skips unavailable models."""
    accounts = [
        MockAccount("account1", unavailable_models={"hy3"}),
        MockAccount("account2"),
        MockAccount("account3")
    ]

    balancer = LoadBalancer(accounts)

    # Should skip account1 and select account2
    account = balancer.select_account("hy3")
    assert account.account_id == "account2"


def test_all_accounts_unavailable():
    """Test error when all accounts are unavailable."""
    accounts = [
        MockAccount("account1", unavailable_models={"hy3"}),
        MockAccount("account2", unavailable_models={"hy3"})
    ]

    balancer = LoadBalancer(accounts)

    with pytest.raises(ValueError, match="All accounts are unavailable"):
        balancer.select_account("hy3")


def test_no_accounts():
    """Test error when no accounts are configured."""
    balancer = LoadBalancer([])
    with pytest.raises(ValueError, match="No accounts available"):
        balancer.select_account()


def test_round_robin_wraps_around():
    """Test round-robin wraps around after exhausting list."""
    accounts = [
        MockAccount("account1"),
        MockAccount("account2")
    ]

    balancer = LoadBalancer(accounts)

    # First 2 selections
    assert balancer.select_account().account_id == "account1"
    assert balancer.select_account().account_id == "account2"

    # Should wrap around to account1
    assert balancer.select_account().account_id == "account1"
