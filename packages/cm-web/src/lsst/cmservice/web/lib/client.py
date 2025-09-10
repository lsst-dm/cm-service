from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

import httpx

from ..settings import settings
from .logging import LOGGER

_atransport = httpx.AsyncHTTPTransport(
    verify=False,
    retries=3,
)
"""An asynchronous HTTP transport for httpx clients."""

_transport = httpx.HTTPTransport(
    verify=False,
    retries=3,
)
"""A synchronous HTTP transport for httpx clients."""

logger = LOGGER.bind(module=__name__)


@asynccontextmanager
async def aget_client() -> AsyncGenerator[httpx.AsyncClient]:
    """Context manager wrapper around an asynchronous httpx client generator"""
    headers = {}
    if settings.auth_token is not None:
        headers["Authorization"] = f"Bearer {settings.auth_token}"

    async with httpx.AsyncClient(
        base_url=f"{settings.base_url}/{settings.api_version}",
        follow_redirects=True,
        transport=_atransport,
        headers=headers,
    ) as client:
        yield client


@contextmanager
def http_client() -> Generator[httpx.Client]:
    """Context manager wrapper around the synchronous httpx client generator"""
    yield from get_client()


def get_client() -> Generator[httpx.Client]:
    """Constructs and yields a synchronous httpx client."""
    headers = {}
    if settings.auth_token is not None:
        headers["Authorization"] = f"Bearer {settings.auth_token}"
    with httpx.Client(
        base_url=f"{settings.base_url}/{settings.api_version}",
        follow_redirects=True,
        transport=_transport,
        headers=headers,
    ) as client:
        try:
            yield client
        except Exception:
            logger.exception()
