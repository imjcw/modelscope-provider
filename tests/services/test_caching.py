"""Test cases for caching utilities."""
import pytest
import time
from provider.services.caching import LRUCache


class TestLRUCache:
    def test_basic_get_set(self):
        """Test basic get/set operations."""
        cache = LRUCache(maxsize=100, ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = LRUCache(maxsize=100, ttl=0.1)  # 100ms TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.15)  # Wait for expiration
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = LRUCache(maxsize=3, ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # This should evict key1

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_clear_cache(self):
        """Test cache clearing."""
        cache = LRUCache(maxsize=100, ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_size(self):
        """Test cache size reporting."""
        cache = LRUCache(maxsize=100, ttl=60)
        assert cache.size() == 0
        cache.set("key1", "value1")
        assert cache.size() == 1
        cache.set("key2", "value2")
        assert cache.size() == 2

    def test_no_ttl_expiration(self):
        """Test that cache with ttl=None never expires."""
        cache = LRUCache(maxsize=100, ttl=None)
        cache.set("key1", "value1")
        time.sleep(0.05)
        assert cache.get("key1") == "value1"

    def test_update_existing_key(self):
        """Test that updating an existing key refreshes position."""
        cache = LRUCache(maxsize=2, ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key1", "value1_updated")  # Update key1, moves to end
        cache.set("key3", "value3")  # Should evict key2 (oldest), not key1

        assert cache.get("key2") is None  # key2 evicted
        assert cache.get("key1") == "value1_updated"
        assert cache.get("key3") == "value3"