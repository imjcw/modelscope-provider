import pytest
from unittest.mock import AsyncMock, Mock
from provider.models.alias_resolver import ModelAliasResolver


class MockAccount:
    """Mock ModelScopeAccount for testing."""
    def __init__(self, account_id: str, api_key: str, base_url: str):
        self.account_id = account_id
        self.api_key = api_key
        self.base_url = base_url


@pytest.mark.asyncio
async def test_resolve_alias_success():
    """Test successful alias resolution."""
    mock_response = {
        "data": [{
            "id": "hy3 overseas",
            "object": "model",
            "created": 1234567890,
            "owned_by": "modelscope"
        }],
        "object": "list"
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=Mock(
        status_code=200,
        json=lambda: mock_response,
        raise_for_status=lambda: None
    ))

    account = MockAccount("test", "test-key", "https://api.inference.modelscope.cn/v1")
    resolver = ModelAliasResolver(mock_client)
    result = await resolver.resolve_alias(account, "hy3")

    assert result == "hy3 overseas"


@pytest.mark.asyncio
async def test_resolve_alias_not_found():
    """Test alias resolution when model not found."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=Mock(
        status_code=200,
        json=lambda: {"data": [], "object": "list"},
        raise_for_status=lambda: None
    ))

    account = MockAccount("test", "test-key", "https://api.inference.modelscope.cn/v1")
    resolver = ModelAliasResolver(mock_client)

    with pytest.raises(ValueError, match="No models found"):
        await resolver.resolve_alias(account, "nonexistent")


@pytest.mark.asyncio
async def test_resolve_alias_http_error():
    """Test alias resolution on HTTP error."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("HTTP 500"))

    account = MockAccount("test", "test-key", "https://api.inference.modelscope.cn/v1")
    resolver = ModelAliasResolver(mock_client)

    with pytest.raises(ValueError, match="Failed to resolve"):
        await resolver.resolve_alias(account, "test-model")
