import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2

from ..settings import settings

_atransport = httpx2.AsyncHTTPTransport(
    verify=False,
    retries=3,
)
"""An asynchronous HTTP transport for httpx2 clients."""

_transport = httpx2.HTTPTransport(
    verify=False,
    retries=3,
)
"""A synchronous HTTP transport for httpx2 clients."""


class ClientFactory:
    _atransport: httpx2.AsyncHTTPTransport
    _client: httpx2.AsyncClient | None
    _headers: dict[str, str]
    _kwargs: dict
    _lock: asyncio.Lock

    def __init__(self) -> None:
        self._atransport = _atransport
        self._transport = _transport
        self._lock = asyncio.Lock()
        self._client = None
        self._headers = {}
        if settings.auth_token is not None:
            self._headers["Authorization"] = f"Bearer {settings.auth_token}"
        self._kwargs = {
            "base_url": f"{settings.base_url}/{settings.api_version}",
            "follow_redirects": True,
            "transport": self._atransport,
            "headers": self._headers,
            "limits": {
                "max_connections": 100,
                "max_keepalive_connections": 20,
                "keepalive_expiry": 30.0,
            },
            "timeout": settings.timeout,
        }

    async def get_aclient(self) -> httpx2.AsyncClient:
        """Get a shared client"""
        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx2.AsyncClient(**self._kwargs)
        return self._client

    @asynccontextmanager
    async def aclient(self) -> AsyncGenerator[httpx2.AsyncClient]:
        client = await self.get_aclient()
        try:
            yield client
        except httpx2.HTTPStatusError:
            # Do not reraise status errors from here, let the caller handle it
            pass
        except Exception:
            raise

    async def close(self) -> None:
        async with self._lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None


CLIENT_FACTORY = ClientFactory()
