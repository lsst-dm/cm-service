from datetime import datetime, timedelta
from time import sleep

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.future import select

from lsst.cmservice.db.queue import Queue


async def daemon_iteration(session: async_scoped_session) -> None:
    queue_entries = await session.execute(select(Queue).where(Queue.time_next_check < datetime.now()))

    for (queue_entry,) in queue_entries:
        queued_node = await queue_entry.get_node(session)
        print(f"Processing queue_entry f{queued_node.fullname}")
        await queue_entry.process_node(session)
        sleep_time = await queue_entry.node_sleep_time(session)
        queue_entry.time_next_check = datetime.now() + timedelta(seconds=sleep_time)

    await session.commit()


async def daemon_loop(session: async_scoped_session) -> None:  # pragma: no cover
    while True:
        await daemon_iteration(session)
        sleep(15)
