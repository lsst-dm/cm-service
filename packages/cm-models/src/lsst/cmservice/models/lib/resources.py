from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx2


class Resource:
    """Wrapper class for resource operations, including http clients."""

    @classmethod
    @asynccontextmanager
    async def http_async_client(cls, *, verify_host: bool = True) -> AsyncGenerator[httpx2.AsyncClient]:
        """Generate a client session for http API operations."""
        transport = httpx2.AsyncHTTPTransport(
            verify=verify_host,
            retries=3,
        )
        async with httpx2.AsyncClient(transport=transport) as session:
            yield session

    @staticmethod
    async def get_resource(uri: str) -> Any:
        """..."""
        ...
