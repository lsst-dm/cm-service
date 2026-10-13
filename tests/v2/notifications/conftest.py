import asyncio
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text

from lsst.cmservice.db.session import DatabaseManager
from lsst.cmservice.models.db import Base, raw
from lsst.cmservice.notifications.task import Notifier


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def pubsubdb(testdb: DatabaseManager) -> AsyncGenerator:
    """Set up notification trigger and function on testdb"""
    assert testdb.engine is not None
    async with testdb.engine.begin() as aconn:
        await aconn.execute(text(raw.NOTIFICATION_FUNCTION.format(schema=Base.metadata.schema)))
        await aconn.execute(text(raw.NOTIFICATION_TRIGGER.format(schema=Base.metadata.schema)))
        await aconn.commit()
    yield testdb
    async with testdb.engine.begin() as aconn:
        await aconn.execute(text("DROP TRIGGER IF EXISTS notification_events_trigger ON activity_log_v2;"))
        await aconn.execute(text("DROP FUNCTION IF EXISTS notify_event_listeners();"))
        await aconn.commit()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def notifications_tg(pubsubdb: DatabaseManager) -> AsyncGenerator:
    shutdown_signal = asyncio.Event()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(Notifier(None, shutdown_signal).task(), name="notifier")
        yield
        shutdown_signal.set()
