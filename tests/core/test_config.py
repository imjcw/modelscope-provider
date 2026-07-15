import os
import pytest
from provider.core.config import ConfigManager
from provider.models.account import ModelScopeAccount


@pytest.fixture(autouse=True)
def setup_env_vars(monkeypatch):
    """Setup environment variables for testing."""
    monkeypatch.setenv("MODELSCOPE_ACCOUNTS_JSON", """[
        {"account_id": "test1", "api_key": "key1", "base_url": "https://api.inference.modelscope.cn/v1/chat/completions"},
        {"account_id": "test2", "api_key": "key2", "base_url": "https://api.inference.modelscope.cn/v1/chat/completions"}
    ]""")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///modelscope_proxy_test.db")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


def test_load_accounts_from_env():
    """Test loading accounts from environment variable."""
    accounts = ConfigManager.load_accounts_from_env()
    assert isinstance(accounts, list)
    assert len(accounts) == 2
    assert all(isinstance(acc, ModelScopeAccount) for acc in accounts)


def test_get_database_url():
    """Test getting database URL."""
    db_url = ConfigManager.get_database_url()
    assert db_url == "sqlite:///modelscope_proxy_test.db"


def test_get_log_level():
    """Test getting log level."""
    log_level = ConfigManager.get_log_level()
    assert log_level == "INFO"


def test_load_accounts_missing_env():
    """Test error when environment variable is missing."""
    # This test requires the env var to be unset
    # Use monkeypatch in the test itself
    import os
    old_value = os.environ.pop("MODELSCOPE_ACCOUNTS_JSON", None)
    try:
        with pytest.raises(ValueError, match="MODELSCOPE_ACCOUNTS_JSON environment variable is not set"):
            ConfigManager.load_accounts_from_env()
    finally:
        if old_value:
            os.environ["MODELSCOPE_ACCOUNTS_JSON"] = old_value


def test_load_accounts_invalid_json():
    """Test error when environment variable contains invalid JSON."""
    import os
    old_value = os.environ.get("MODELSCOPE_ACCOUNTS_JSON")
    os.environ["MODELSCOPE_ACCOUNTS_JSON"] = "invalid json"
    try:
        with pytest.raises(ValueError, match="Failed to parse MODELSCOPE_ACCOUNTS_JSON"):
            ConfigManager.load_accounts_from_env()
    finally:
        if old_value:
            os.environ["MODELSCOPE_ACCOUNTS_JSON"] = old_value
