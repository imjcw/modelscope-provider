import pytest
from unittest.mock import AsyncMock, Mock
from provider.models.alias_resolver import ModelAliasResolver


class MockAccount:
    """Mock ModelScopeAccount for testing."""
    def __init__(self, account_id: str, api_key: str, base_url: str):
        self.account_id = account_id
        self.api_key = api_key
        self.base_url = base_url


class MockMappingRepo:
    """Mock MappingRepository for testing."""
    def __init__(self, mappings):
        self.mappings = mappings  # dict: alias_name -> list[dict]

    def find_by_alias(self, alias_name: str):
        return self.mappings.get(alias_name, [])


@pytest.mark.asyncio
async def test_resolve_alias_success():
    """Test alias resolution via the local model_mappings table."""
    mock_repo = MockMappingRepo({
        "hy3": [{"alias_name": "hy3", "region": "overseas", "actual_model_id": "hy3 overseas"}],
    })
    mock_client = AsyncMock()  # HTTP path must NOT be exercised

    account = MockAccount("test", "test-key", "https://api.inference.modelscope.cn/v1")
    resolver = ModelAliasResolver(mock_client, mapping_repo=mock_repo)
    result = await resolver.resolve_alias(account, "hy3")

    assert result == "hy3 overseas"
    # Verify HTTP was never called (mapping lookup short-circuited)
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_alias_not_found():
    """Test that when the mapping repo returns empty, HTTP fallback is used and
    a ValueError is raised when no models are returned by the API."""
    mock_repo = MockMappingRepo({})  # no mapping for the alias -> fall through to HTTP
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=Mock(
        status_code=200,
        json=lambda: {"data": [], "object": "list"},
        raise_for_status=lambda: None
    ))

    account = MockAccount("test", "test-key", "https://api.inference.modelscope.cn/v1")
    resolver = ModelAliasResolver(mock_client, mapping_repo=mock_repo)

    with pytest.raises(ValueError, match="No models found"):
        await resolver.resolve_alias(account, "nonexistent")


@pytest.mark.asyncio
async def test_resolve_alias_http_error():
    """Test that when no mapping exists, an HTTP error propagates as ValueError."""
    mock_repo = MockMappingRepo({})  # no mapping -> HTTP path exercised
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("HTTP 500"))

    account = MockAccount("test", "test-key", "https://api.inference.modelscope.cn/v1")
    resolver = ModelAliasResolver(mock_client, mapping_repo=mock_repo)

    with pytest.raises(ValueError, match="Failed to resolve"):
        await resolver.resolve_alias(account, "test-model")
