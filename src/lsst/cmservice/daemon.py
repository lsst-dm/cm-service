import asyncio
from datetime import datetime, timedelta
from time import sleep

import structlog
from safir.database import create_async_session, create_database_engine

from .common.daemon import daemon_iteration
from .config import config


async def main_loop() -> None:
    logger = structlog.get_logger(__name__)
    engine = create_database_engine(config.db.url, config.db.password)

    async with engine.begin():
        session = await create_async_session(engine, logger)

        logger.info("Daemon starting.")

        last_log_time = datetime.now()
        iteration_count = 0
        delta_seconds = 300
        while True:
            if datetime.now() - last_log_time > timedelta(seconds=delta_seconds):
                logger.info(f"Daemon completed {iteration_count} iterations in {delta_seconds} seconds.")
                last_log_time = datetime.now()
            await daemon_iteration(session)
            sleep(15)


def main() -> None:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_loop())


if __name__ == "__main__":
    main()
