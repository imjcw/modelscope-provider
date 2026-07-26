"""Test cases for ModelAliasResolver caching."""
import pytest
import httpx
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


def make_mock_http_client():
    """Create a mock HTTP client."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_alias_resolver_caches_404_responses():
    """Test that 404 responses are cached to avoid repeated HTTP calls."""
    http_client = make_mock_http_client()
    resolver = ModelAliasResolver(http_client, MockMappingRepo({}))

    # Mock a 404 HTTPStatusError properly
    mock_response = Mock()
    mock_response.status_code = 404
    http_error = httpx.HTTPStatusError(
        "Not Found", request=Mock(), response=mock_response
    )
    http_client.get.side_effect = http_error

    account = MockAccount("acc1", "key1", "https://api.test.com")

    result1 = await resolver.resolve_alias(account, "non-existent-model")
    assert result1 == "non-existent-model"  # 404 returns alias as-is
    assert http_client.get.call_count == 1

    # Second call - should use cache, not make HTTP request
    result2 = await resolver.resolve_alias(account, "non-existent-model")
    assert result2 == "non-existent-model"
    assert http_client.get.call_count == 1  # Still 1, not 2


@pytest.mark.asyncio
async def test_alias_resolver_caches_successful_responses():
    """Test that successful resolutions are cached."""
    http_client = make_mock_http_client()
    resolver = ModelAliasResolver(http_client, MockMappingRepo({}))

    # First call - successful resolution
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={"data": [{"id": "actual-model-id"}]})
    mock_response.raise_for_status = Mock()
    http_client.get.return_value = mock_response

    account = MockAccount("acc1", "key1", "https://api.test.com")

    result1 = await resolver.resolve_alias(account, "some-model")
    assert result1 == "actual-model-id"
    assert http_client.get.call_count == 1

    # Second call - should use cache
    result2 = await resolver.resolve_alias(account, "some-model")
    assert result2 == "actual-model-id"
    assert http_client.get.call_count == 1  # Still 1, not 2


@pytest.mark.asyncio
async def test_alias_resolver_respects_cache_ttl_differences():
    """Test that 404s and successful resolutions cache independently."""
    http_client = make_mock_http_client()
    resolver = ModelAliasResolver(http_client, MockMappingRepo({}))

    account = MockAccount("acc1", "key1", "https://api.test.com")

    # First call to alias1 - success
    success_response = Mock()
    success_response.status_code = 200
    success_response.json = Mock(return_value={"data": [{"id": "model-123"}]})
    success_response.raise_for_status = Mock()
    http_client.get.return_value = success_response
    result1 = await resolver.resolve_alias(account, "alias1")
    assert result1 == "model-123"

    # First call to alias2 - 404
    fail_response = Mock()
    fail_response.status_code = 404
    http_error = httpx.HTTPStatusError(
        "Not Found", request=Mock(), response=fail_response
    )
    http_client.get.side_effect = http_error
    result2 = await resolver.resolve_alias(account, "alias2")
    assert result2 == "alias2"

    # Both caches are populated independently
    assert resolver.success_cache.size() == 1
    assert resolver.failure_cache.size() == 1


@pytest.mark.asyncio
async def test_alias_resolver_bypasses_cache_for_mapping_table_hits():
    """Test that cache is bypassed when mapping table lookup succeeds."""
    # Setup mapping repo with direct mapping
    mapping_repo = MockMappingRepo({
        "my-alias": [{"alias_name": "my-alias", "actual_model_id": "mapped-model"}]
    })

    http_client = make_mock_http_client()
    resolver = ModelAliasResolver(http_client, mapping_repo)

    account = MockAccount("acc1", "key1", "https://api.test.com")

    result = await resolver.resolve_alias(account, "my-alias")
    assert result == "mapped-model"
    http_client.get.assert_not_called()  # No HTTP call
    # Cache should be empty since we didn't go through HTTP path


def test_alias_resolver_clear_cache():
    """Test clear_cache method."""
    resolver = ModelAliasResolver(Mock(), MockMappingRepo({}))

    # Access internal caches to verify they exist
    assert hasattr(resolver, 'success_cache')
    assert hasattr(resolver, 'failure_cache')

    # Test clear method works
    resolver.clear_cache()

    # Verify caches are empty after clear
    assert resolver.success_cache.size() == 0
    assert resolver.failure_cache.size() == 0