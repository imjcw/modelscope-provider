import logging
import httpx
from models.account import ModelScopeAccount
from services.caching import LRUCache

logger = logging.getLogger(__name__)


class ModelAliasResolver:
    """Resolve model aliases to actual model IDs with caching.

    Resolution priority:
    1. If a mapping_repo is provided, look up the alias in the model_mappings
       table. If a mapping exists, return its actual_model_id immediately.
    2. Check the in-memory cache for previously resolved aliases (success or
       404 failure). This avoids repeating the HTTP round-trip for models
       that always 404, which was the main per-request latency contributor.
    3. Fall through to HTTP-based resolution (the ModelScope API model
       endpoint) and cache the result.
    """

    def __init__(self, http_client: httpx.AsyncClient, mapping_repo=None):
        self.http_client = http_client
        self.mapping_repo = mapping_repo
        # Cache successful resolutions for 5 minutes — model IDs rarely change
        self.success_cache = LRUCache(maxsize=1000, ttl=300)
        # Cache 404 ("alias not found, use as-is") for 1 hour — these almost
        # never recover, and re-checking on every request wastes 100-350ms.
        self.failure_cache = LRUCache(maxsize=1000, ttl=3600)

    async def resolve_alias(self, account: ModelScopeAccount, alias: str) -> str:
        """Resolve model alias to actual model ID.

        Caches both successful resolutions and 404 failures keyed by
        (account_id, alias) so repeated requests for the same alias skip
        the HTTP round-trip entirely.
        """
        # Step 1: check the local model_mappings table first
        if self.mapping_repo is not None:
            mappings = self.mapping_repo.find_by_alias(alias)
            if mappings:
                actual_model_id = mappings[0]["actual_model_id"]
                logger.info(
                    f"Resolved alias '{alias}' to model ID '{actual_model_id}' "
                    f"via model_mappings table for account {account.account_id}"
                )
                return actual_model_id

        # Step 2: check caches before hitting the network
        cache_key = f"{account.account_id}:{alias}"

        cached_success = self.success_cache.get(cache_key)
        if cached_success is not None:
            logger.debug(
                f"Cache hit (success) for alias '{alias}', "
                f"account {account.account_id}"
            )
            return cached_success

        if self.failure_cache.get(cache_key) is not None:
            logger.debug(
                f"Cache hit (failure) for alias '{alias}', "
                f"account {account.account_id}"
            )
            return alias  # Return alias as-is for cached 404s

        # Step 3: fall through to HTTP-based resolution
        actual_id = await self._fetch_model_id(account, alias)

        # Cache the result. A 404 returns the alias unchanged — cache it as a
        # failure so we don't keep re-hitting the API. Other errors raise and
        # are NOT cached (transient failures should be retried).
        if actual_id == alias:
            self.failure_cache.set(cache_key, True)
        else:
            self.success_cache.set(cache_key, actual_id)

        return actual_id

    async def _fetch_model_id(self, account: ModelScopeAccount, alias: str) -> str:
        """Fetch model ID from ModelScope API."""
        url = f"{account.base_url.rstrip('/')}/models/{alias}"
        logger.info(f"Fetching model ID for alias '{alias}' from {account.account_id}")
        try:
            response = await self.http_client.get(
                url,
                headers={"Authorization": f"Bearer {account.api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            # Some providers (e.g. Vercel AI Gateway) return a single model
            # object instead of OpenAI-standard {"data": [...]}.
            if isinstance(data, list):
                models = data
            elif isinstance(data, dict) and data.get("data"):
                models = data["data"]
            elif isinstance(data, dict) and "id" in data:
                # Single object response
                return data["id"]
            else:
                models = []
            if not models:
                raise ValueError(f"No models found for alias '{alias}'")
            actual_id = models[0]["id"]
            logger.info(f"Resolved alias '{alias}' to model ID '{actual_id}'")
            return actual_id
        except httpx.HTTPStatusError as e:
            # If model alias API doesn't exist, returns 404, or is blocked
            # by WAF/Cloudflare (403), just use the alias as-is. Some upstream
            # providers (e.g. routeway.ai, kilo.ai) don't expose a /models/{id}
            # lookup endpoint at all (405 Method Not Allowed).
            if e.response.status_code in (403, 404, 405):
                logger.warning(
                    f"Model alias API not available for '{alias}' "
                    f"({e.response.status_code}), using as-is"
                )
                return alias
            logger.error(f"Failed to fetch model ID: {e}")
            raise ValueError(f"Failed to resolve model alias '{alias}': {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error fetching model ID: {e}")
            raise ValueError(f"Failed to resolve model alias '{alias}': {str(e)}")

    def clear_cache(self):
        """Clear both caches.

        Called after account or mapping changes to ensure stale entries don't
        persist (see AdminService cache invalidation).
        """
        self.success_cache.clear()
        self.failure_cache.clear()
        logger.info("ModelAliasResolver caches cleared")