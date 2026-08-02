"""Tests for HttpClient multi-API-key selection (_get_active_keys).

Verifies the fix for the dead multi-key feature: when an account carries
``api_key_records`` (list of dicts), the client must extract the ``api_key``
strings and skip frozen keys — previously it returned the raw dicts (breaking
header construction) and the records were never populated anyway.
"""
from provider.core.http_client import HttpClient


class _Account:
    def __init__(self, api_key="primary", api_key_records=None, api_keys=None):
        self.api_key = api_key
        self.api_key_records = api_key_records
        if api_keys is not None:
            self.api_keys = api_keys


def test_records_extract_key_strings():
    """api_key_records (dicts) should yield api_key strings, not dicts."""
    client = HttpClient()
    account = _Account(api_key_records=[
        {"api_key": "k1", "status": "active"},
        {"api_key": "k2", "status": "active"},
    ])
    keys = client._get_active_keys(account)
    assert keys == ["k1", "k2"]
    assert all(isinstance(k, str) for k in keys)


def test_records_skip_frozen_keys():
    """Frozen keys should be excluded from rotation."""
    client = HttpClient()
    account = _Account(api_key_records=[
        {"api_key": "k1", "status": "active"},
        {"api_key": "k2", "status": "frozen"},
        {"api_key": "k3", "status": "active"},
    ])
    keys = client._get_active_keys(account)
    assert keys == ["k1", "k3"]


def test_falls_back_to_api_keys_list():
    """Without records, use the api_keys string list."""
    client = HttpClient()
    account = _Account(api_key="primary", api_keys=["a", "b"])
    account.api_key_records = None
    assert client._get_active_keys(account) == ["a", "b"]


def test_falls_back_to_primary_key():
    """Without records or api_keys, fall back to the single primary key."""
    client = HttpClient()
    account = _Account(api_key="primary")
    account.api_key_records = None
    account.api_keys = []
    assert client._get_active_keys(account) == ["primary"]
