from asyncio import create_task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from anyio import current_time, sleep_until
from fastapi import FastAPI
from safir.database import create_async_session, create_database_engine
from safir.logging import configure_uvicorn_logging

from . import __version__
from .common.daemon import daemon_iteration
from .common.logging import LOGGER
from .config import config
from .routers.healthz import health_router

configure_uvicorn_logging(config.logging.level)

logger = LOGGER.bind(module=__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # start
    app.state.tasks = set()
    daemon = create_task(main_loop(), name="daemon")
    app.state.tasks.add(daemon)
    yield
    # stop


async def main_loop() -> None:
    """Daemon execution loop.

    With a database session, perform a single daemon interation and then sleep
    until the next daemon appointment.
    """
    engine = create_database_engine(config.db.url, config.db.password)
    sleep_time = config.daemon.processing_interval

    async with engine.begin():
        session = await create_async_session(engine, logger)
        logger.info("Daemon starting.")
        _iteration_count = 0

        while True:
            _iteration_count += 1
            logger.info("Daemon starting iteration.")
            await daemon_iteration(session)
            _iteration_time = current_time()
            logger.info(f"Daemon completed {_iteration_count} iterations at {_iteration_time}.")
            _next_wakeup = _iteration_time + sleep_time
            logger.info(f"Daemon next iteration at {_next_wakeup}.")
            await sleep_until(_next_wakeup)


def main() -> None:
    app = FastAPI(
        lifespan=lifespan,
        version=__version__,
    )

    app.include_router(health_router)

    uvicorn.run(app, host=config.asgi.host, port=config.asgi.port, reload=config.asgi.reload)


if __name__ == "__main__":
    main()
