"""TTL cache for the OpenAI-compatible /v1/models list.

``/v1/models`` is requested on every chat-completion warm-up by some OpenAI
clients, so we cache the (rarely-changing) mapping-derived list for a short
TTL instead of re-scanning the mapping table on every request.  The cache is
invalidated whenever the mapping table is mutated (see ``invalidate``).
"""
import time
from typing import Callable, List

_MODELS_CACHE_TTL = 15.0  # seconds
_cache: dict = {"data": None, "ts": 0.0}


def get_models(loader: Callable[[], List[dict]]) -> List[dict]:
    """Return the cached model list, recomputing via ``loader`` when stale.

    ``loader`` is a zero-arg callable returning the list of active model dicts.
    """
    now = time.monotonic()
    cached = _cache["data"]
    if cached is not None and (now - _cache["ts"]) < _MODELS_CACHE_TTL:
        return cached
    data = loader()
    _cache["data"] = data
    _cache["ts"] = now
    return data


def invalidate() -> None:
    """Drop the cached /v1/models list so the next request recomputes it."""
    _cache["data"] = None
    _cache["ts"] = 0.0
