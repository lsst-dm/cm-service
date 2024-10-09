from datetime import datetime, timedelta
from time import sleep

from sqlalchemy.future import select

from lsst.cmservice.db.queue import Queue


async def daemon_iteration(session) -> None:
    queue_entries = await session.execute(select(Queue).where(Queue.time_next_check < datetime.now()))

    for (queue_entry,) in queue_entries:
        queued_element = await queue_entry.get_element()
        print(f"Processing queue_entry f{queued_element.fullname}")
        await queue_entry.process_element(session)
        sleep_time = await queue_entry.element_sleep_time(session)
        queue_entry.time_next_check = datetime.now() + timedelta(seconds=sleep_time)


async def daemon_loop(session) -> None:
    while True:
        daemon_iteration(session)
        sleep(15)
