"""Generic caching utilities with LRU eviction and TTL support.

Used by the proxy to cache model alias resolutions and other expensive
lookup operations, avoiding repeated HTTP calls and database queries
on every API request.
"""
import time
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """LRU cache with TTL support.

    Thread-safe writes are not guaranteed — this is designed for use
    in a single-threaded async context (FastAPI event loop).

    Args:
        maxsize: Maximum number of items in cache before eviction.
        ttl: Time to live in seconds (None for no expiration).
    """

    def __init__(self, maxsize: int = 1000, ttl: Optional[float] = None):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = OrderedDict()

    def set(self, key: Any, value: Any):
        """Set a key-value pair in cache.

        If the key already exists, it is moved to the end (most recently used).
        If the cache is full, the oldest entry is evicted.
        """
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.maxsize:
            self.cache.popitem(last=False)  # Remove oldest (first inserted)

        self.cache[key] = {
            "value": value,
            "timestamp": time.time(),
        }

    def get(self, key: Any) -> Optional[Any]:
        """Get value by key.

        Returns None if the key is not found or the TTL has expired.
        On hit, the key is moved to the end (most recently used).
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # Check TTL expiry
        if self.ttl is not None and (time.time() - entry["timestamp"]) > self.ttl:
            del self.cache[key]
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return entry["value"]

    def clear(self):
        """Clear all cached items."""
        self.cache.clear()

    def size(self) -> int:
        """Return the current number of items in the cache."""
        return len(self.cache)