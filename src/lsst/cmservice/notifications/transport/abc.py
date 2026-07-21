from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx

from lsst.cmservice.models.db.campaigns import ActivityLog as ActivityLog
from lsst.cmservice.models.enums import ManifestKind, StatusEnum

from ..models import NotificationPayload as NotificationPayload


class NotificationTransport(ABC):
    default_filters: list[str] = ["start:*:running", "end:running:*", "*:*:failed", "breakpoint:*:running"]

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

    async def check_notification_filter(self, filters: list[str], activity_log: ActivityLog) -> bool:
        """Test an activity log subject record against a filter to determine
        whether the log requires a notification
        """
        matches = []
        for filter_ in filters:
            node_kind, from_status, to_status = filter_.split(":")

            match = [
                (node_kind == "*" or ManifestKind[node_kind] is activity_log.subject.kind),
                (from_status == "*" or StatusEnum[from_status] is activity_log.from_status),
                (to_status == "*" or StatusEnum[to_status] is activity_log.to_status),
            ]
            matches.append(all(match))
        return any(matches)
