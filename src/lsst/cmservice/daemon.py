import os
from asyncio import TaskGroup
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from anyio import current_time, sleep_until
from fastapi import FastAPI

from . import __version__
from .common.butler import BUTLER_FACTORY  # noqa: F401
from .common.daemon import daemon_iteration
from .common.daemon_v2 import DaemonContext
from .common.daemon_v2 import daemon_iteration as daemon_iteration_v2
from .common.flags import Features
from .common.logging import LOGGER, LoggingMiddleware
from .common.panda import get_panda_token
from .common.scheduler import Scheduler
from .config import config
from .db.session import db_session_dependency
from .routers.healthz import health_router

logger = LOGGER.bind(module=__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # start
    # Bootstrap a panda id token
    _ = get_panda_token()
    # Update process environment with configuration models
    os.environ |= config.panda.model_dump(by_alias=True, exclude_none=True)
    os.environ |= config.htcondor.model_dump(by_alias=True, exclude_none=True)
    app.state.tasks = set()
    # Dependency inits before app starts running
    await db_session_dependency.initialize()
    assert db_session_dependency.engine is not None

    async with TaskGroup() as tg:
        # Daemon
        daemon = tg.create_task(main_loop(app=app), name="daemon")
        app.state.tasks.add(daemon)

        # Scheduler
        if Features.SCHEDULER in config.features.enabled:
            scheduler = Scheduler(app=app)
            scheduler_task = tg.create_task(scheduler.scheduler_task(), name="scheduler")
            app.state.tasks.add(scheduler_task)

        yield
        # Tasks are cancelled at the end of the taskgroup

    # stop
    await db_session_dependency.aclose()


async def main_loop(app: FastAPI) -> None:
    """Daemon execution loop.

    With a database session, perform a single daemon interation and then sleep
    until the next daemon appointment.
    """
    sleep_time = config.daemon.processing_interval

    if db_session_dependency.sessionmaker is None:
        raise RuntimeError("Database SessionMaker is not ready!")

    logger.info("Starting Daemon...")
    _iteration_count = 0

    while True:
        _iteration_count += 1
        async with DaemonContext(app=app) as context:
            logger.info("Daemon starting iteration %s", _iteration_count)
            if Features.DAEMON_V1 in config.features.enabled:
                await daemon_iteration(context.session)
            if Features.DAEMON_V2 in config.features.enabled:
                await daemon_iteration_v2(context)
            _iteration_time = current_time()
            logger.info("Daemon completed %s iterations at %s.", _iteration_count, _iteration_time)
            _next_wakeup = _iteration_time + sleep_time
            logger.info("Daemon next iteration at %s.", _next_wakeup)
        await sleep_until(_next_wakeup)


def main() -> None:
    app = FastAPI(
        lifespan=lifespan,
        version=__version__,
    )
    app.add_middleware(LoggingMiddleware)

    app.include_router(health_router)

    uvicorn.run(app, host=config.asgi.host, port=config.asgi.port, reload=config.asgi.reload, log_config=None)


if __name__ == "__main__":
    main()
