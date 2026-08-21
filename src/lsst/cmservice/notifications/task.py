"""Worker task for a notification event listener.

The worker acquires a database connection and uses the postgres NOTIFY async
messaging system to receive messages when activity log entries are added to
the database that may require a notification event.

If the payload of such a message includes a transport (`kind`) that the worker
is responsible for, the worker builds a notification message for that transport
based on the referenced activity log message, which is acquired via its id.
"""

import asyncio

from asyncpg import Connection
from fastapi import FastAPI

from lsst.cmservice.models.enums import NotificationLabelEnum
from lsst.cmservice.models.lib.logging import LOGGER

from ..db.session import db_session_dependency
from .transport.abc import NotificationPayload
from .transport.factory import factory

logger = LOGGER.bind(module=__name__)


class Notifier:
    """The notifier class operates a long-lived background task that uses a
    dedicated database connection to subscribe to NOTIFY messages from one
    or more channels.
    """

    def __init__(self, app: FastAPI | None, sentinel: asyncio.Event):
        self.app = app
        self.sentinel = sentinel

    async def task(self) -> None:
        """A coro that is meant to be used with `asyncio.create_task` to
        establish and maintain a perpetual reference to the notifier under-
        lying this class instance.
        """
        async with db_session_dependency.dedicated_async_engine(isolation_level="AUTOCOMMIT") as engine:
            async with engine.connect() as conn:
                raw = await conn.get_raw_connection()
                pg_conn: Connection | None = raw.driver_connection
                if pg_conn is None:
                    raise RuntimeError("No database connection")

                # Add a listener for each channel
                for channel in factory.builders:
                    await pg_conn.add_listener(channel, self.notification_handler)

                try:
                    logger.info("Started notifier")
                    await self.sentinel.wait()
                    logger.info("App is shutting down")
                finally:
                    for channel in factory.builders:
                        await pg_conn.remove_listener(channel, self.notification_handler)

    async def notification_handler(
        self, connection: Connection, pid: int, channel: str, payload_: str
    ) -> None:
        """Callback for database NOTIFY messages.

        Dispatch the payload to the transport responsible for the notification
        as quickly as possible.

        If the channel is "default" then there was no available notification
        label in the database, so we send the payload to the "default"
        transport.
        """
        payload = NotificationPayload.model_validate_json(payload_)
        label = "default" if channel == "default" else payload.label
        factory.build(NotificationLabelEnum[channel], payload.label)
        dispatch = asyncio.wait_for(factory.get(label).deliver(payload), timeout=30.0)
        await dispatch
