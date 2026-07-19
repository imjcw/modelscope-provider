import logging
import httpx
from models.account import ModelScopeAccount

logger = logging.getLogger(__name__)


class ModelAliasResolver:
    """Resolve model aliases to actual model IDs."""

    def __init__(self, http_client: httpx.AsyncClient, mapping_repo=None):
        self.http_client = http_client
        self.mapping_repo = mapping_repo

    async def resolve_alias(self, account: ModelScopeAccount, alias: str) -> str:
        """Resolve model alias to actual model ID.

        Resolution priority:
        1. If a mapping_repo is provided, look up the alias in the model_mappings
           table. If a mapping exists, return its actual_model_id immediately.
        2. Otherwise, fall through to HTTP-based resolution (the ModelScope API
           model endpoint).
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

        # Step 2: fall through to HTTP-based resolution
        return await self._fetch_model_id(account, alias)

    async def _fetch_model_id(self, account: ModelScopeAccount, alias: str) -> str:
        """Fetch model ID from ModelScope API."""
        url = f"{account.base_url}/models/{alias}"
        logger.info(f"Fetching model ID for alias '{alias}' from {account.account_id}")
        try:
            response = await self.http_client.get(
                url,
                headers={"Authorization": f"Bearer {account.api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            models = data.get("data", [])
            if not models:
                raise ValueError(f"No models found for alias '{alias}'")
            actual_id = models[0]["id"]
            logger.info(f"Resolved alias '{alias}' to model ID '{actual_id}'")
            return actual_id
        except httpx.HTTPStatusError as e:
            # If model alias API doesn't exist or returns 404, just use the alias as-is
            if e.response.status_code == 404:
                logger.warning(f"Model alias API not found for '{alias}', using as-is")
                return alias
            logger.error(f"Failed to fetch model ID: {e}")
            raise ValueError(f"Failed to resolve model alias '{alias}': {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error fetching model ID: {e}")
            raise ValueError(f"Failed to resolve model alias '{alias}': {str(e)}")
