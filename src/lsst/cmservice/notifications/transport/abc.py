from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx

from ..models import NotificationPayload as NotificationPayload


class NotificationTransport(ABC):
    @abstractmethod
    def notify(self, message: bytes | dict) -> None:
        """Sends a notification message."""
        ...

    @abstractmethod
    async def anotify(self, message: bytes | dict) -> None:
        """Sends a notification message asynchronously."""
        ...

    @asynccontextmanager
    async def http_async_client(self, *, verify_host: bool = True) -> AsyncGenerator[httpx.AsyncClient]:
        """Generate a client session for http API operations."""
        transport = httpx.AsyncHTTPTransport(
            verify=verify_host,
            retries=3,
        )
        async with httpx.AsyncClient(transport=transport) as session:
            yield session

    @abstractmethod
    async def deliver(self, payload: NotificationPayload) -> None:
        """Task entrypoint for use of notification delivery transport"""
        ...
