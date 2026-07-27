import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HttpClient:
    """HTTP client for making requests to ModelScope API."""

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

    async def request(
        self,
        account,
        method: str,
        url: str,
        **kwargs
    ):
        """Make HTTP request to ModelScope API."""
        client = await self.create_client()

        headers = {
            "Authorization": f"Bearer {account.api_key}",
            "Content-Type": "application/json"
        }

        response = await client.request(
            method,
            url,
            headers=headers,
            **kwargs
        )

        return response

    async def close_all_clients(self):
        """Close all HTTP clients."""
        await self.close()
