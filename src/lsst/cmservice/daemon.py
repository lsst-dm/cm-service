import os
from asyncio import create_task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from anyio import current_time, sleep_until
from fastapi import FastAPI
from safir.logging import configure_uvicorn_logging

from . import __version__
from .common.butler import BUTLER_FACTORY  # noqa: F401
from .common.daemon import daemon_iteration
from .common.logging import LOGGER
from .common.panda import get_panda_token
from .config import config
from .db.session import db_session_dependency
from .routers.healthz import health_router

configure_uvicorn_logging(config.logging.level)

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
    daemon = create_task(main_loop(app=app), name="daemon")
    app.state.tasks.add(daemon)
    yield
    # stop
    await db_session_dependency.aclose()


async def main_loop(app: FastAPI) -> None:
    """Daemon execution loop.

    With a database session, perform a single daemon interation and then sleep
    until the next daemon appointment.
    """
    sleep_time = config.daemon.processing_interval

    session = await anext(db_session_dependency())
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
