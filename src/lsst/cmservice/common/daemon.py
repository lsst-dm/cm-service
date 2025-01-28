from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.future import select

from ..common.logging import LOGGER
from ..config import config
from ..db.queue import Queue
from ..db.script import Script

logger = LOGGER.bind(module=__name__)


async def daemon_iteration(session: async_scoped_session) -> None:
    iteration_start = datetime.now()
    # TODO limit query to queues that do not have a "time_finished"
    queue_entries = await session.execute(select(Queue).where(Queue.time_next_check < iteration_start))
    logger.debug("Daemon Iteration: %s", iteration_start)

    # TODO: should the daemon check any campaigns with a state == prepared that
    #       do not have queues? Queue creation should not be a manual step.
    queue_entry: Queue
    for (queue_entry,) in queue_entries:
        try:
            queued_node = await queue_entry.get_node(session)
            if (
                queued_node.status.is_processable_script()
                if isinstance(queued_node, Script)
                else queued_node.status.is_processable_element()
            ):
                logger.info("Processing queue_entry %s", queued_node.fullname)
                await queue_entry.process_node(session)
                sleep_time = await queue_entry.node_sleep_time(session)
            else:
                # Put this entry to sleep for a while
                sleep_time = config.daemon.processing_interval
            time_next_check = iteration_start + timedelta(seconds=sleep_time)
            queue_entry.time_next_check = time_next_check
            logger.info(f"Next check for {queued_node.fullname} at {time_next_check}")
        except Exception:
            logger.exception()
            continue
    await session.commit()
