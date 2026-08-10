import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HttpClient:
    """HTTP client for making requests to ModelScope API.

    Key rotation is now handled by the router layer (``AliasRouter`` expands
    each active API key into a separate candidate).  This client receives a
    pre-selected ``key_string`` and uses it directly — no internal rotation.

    The ``_get_active_keys`` fallback is retained for the legacy ``LoadBalancer``
    path (no alias bindings), which does not go through key-level expansion.
    """

    def __init__(self, timeout: float = 30.0, read_timeout: float = 3600.0):
        self.timeout = timeout
        self.read_timeout = read_timeout
        self.client: Optional[httpx.AsyncClient] = None

    async def create_client(self) -> httpx.AsyncClient:
        """Create async HTTP client.

        ``read_timeout`` is kept long (default 1 hour) because upstream
        model providers may take a long time to start streaming/sending a
        non-streaming response; a short read timeout causes spurious
        ``httpx.ReadTimeout`` errors. connect/write/pool use the shorter
        ``timeout`` so connection issues fail fast.
        """
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.timeout,
                    read=self.read_timeout,
                    write=self.timeout,
                    pool=self.timeout,
                ),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            )
        return self.client

    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def close_all_clients(self):
        """Close all HTTP clients (alias for compatibility with shutdown code)."""
        await self.close()

    def _build_headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _get_active_keys(self, account) -> list:
        """Get active API key strings from account, skipping frozen ones.

        Used as a fallback for the legacy ``LoadBalancer`` path where the
        router does not pre-select a key.  The main alias-router path passes
        an explicit ``key_string`` instead.
        """
        records = getattr(account, "api_key_records", None)
        if records:
            return [
                r["api_key"]
                for r in records
                if r.get("status") != "frozen" and r.get("api_key")
            ]

        api_keys = getattr(account, "api_keys", None) or [account.api_key]
        return api_keys

    async def request(
        self,
        account,
        method: str,
        url: str,
        stream: bool = False,
        key_string: str = None,
        **kwargs
    ):
        """Make HTTP request to ModelScope API.

        ``key_string`` is the API key to use, pre-selected by the router.
        When ``None`` (legacy path), the first active key from the account
        is used.

        When ``stream=True`` the response body is NOT pre-read: the caller
        gets an httpx.Response whose body must be consumed via
        ``aiter_lines()/aiter_bytes()`` and finally ``aclose()``. This is
        required for SSE — otherwise httpx buffers the whole body before
        returning, and the client receives everything at once at the end.
        """
        client = await self.create_client()

        # Determine the API key to use.
        if key_string is not None:
            api_key = key_string
        else:
            # Legacy path: pick the first active key.
            keys = self._get_active_keys(account)
            api_key = keys[0] if keys else getattr(account, "api_key", None)

        # Guard against a missing key. The legacy LoadBalancer path can reach
        # here with no usable key (api_key is None), which would otherwise
        # crash on `len(api_key)` and build a "Bearer None" header. Fail loud
        # but cleanly — the caller converts this to a 502.
        if not api_key:
            account_id = getattr(account, "account_id", "?")
            logger.error("No usable API key for account %s", account_id)
            raise ValueError(f"No usable API key configured for account {account_id}")

        headers = self._build_headers(api_key)
        key_suffix = api_key[-8:] if len(api_key) > 8 else "***"
        logger.info(
            "Request %s %s with key ending ...%s",
            method, url, key_suffix,
        )

        if stream:
            req = client.build_request(method, url, headers=headers, **kwargs)
            return await client.send(req, stream=True)
        return await client.request(method, url, headers=headers, **kwargs)