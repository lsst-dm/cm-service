import asyncio
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text

from lsst.cmservice.config import config
from lsst.cmservice.db.session import DatabaseManager
from lsst.cmservice.models.db import raw
from lsst.cmservice.notifications.task import Notifier


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def pubsubdb(testdb: DatabaseManager) -> AsyncGenerator:
    """Set up notification trigger and function on testdb.

    These objects are created in the test schema and are dropped along with it
    by the `testdb` fixture.
    """
    assert testdb.engine is not None
    async with testdb.engine.begin() as aconn:
        await aconn.execute(text(raw.NOTIFICATION_FUNCTION.format(schema=config.db.table_schema)))
        await aconn.execute(text(raw.NOTIFICATION_TRIGGER.format(schema=config.db.table_schema)))
    yield testdb


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def notifications_tg(pubsubdb: DatabaseManager) -> AsyncGenerator:
    shutdown_signal = asyncio.Event()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(Notifier(None, shutdown_signal).task(), name="notifier")
        yield
        shutdown_signal.set()
