from asyncio import create_task, sleep
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import structlog
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from safir.database import create_async_session, create_database_engine

from . import __version__
from .common.daemon import daemon_iteration
from .config import config


class State:
    """A class defining an application State object.

    Attributes
    ----------
    tasks : set
        Set of coroutine tasks that have been added to the event loop.
    """

    tasks: set

    def __init__(self) -> None:
        self.tasks = set()


health_router = APIRouter()
"""An API Router for a health endpoint"""

state = State()
"""A global State object"""


@health_router.get("/healthz", tags=["internal", "health"])
async def get_healthz() -> dict:
    server_ok = True
    health_response = {}

    for task in state.tasks:
        task_response: dict[str, bool | str | None] = {"task_running": True, "task_exception": None}
        if task.done():
            server_ok = False
            task_response["task_running"] = False
            task_response["task_exception"] = str(task.exception())
        health_response[task.get_name()] = task_response

    if not server_ok:
        raise HTTPException(status_code=500, detail=health_response)
    else:
        return health_response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator:
    # start
    daemon = create_task(main_loop(), name="daemon")
    state.tasks.add(daemon)
    yield
    # stop


async def main_loop() -> None:
    logger = structlog.get_logger(config.logger_name)
    engine = create_database_engine(config.database_url, config.database_password)

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
            await sleep(15)


def main() -> None:
    app = FastAPI(
        lifespan=lifespan,
        version=__version__,
    )

    app.include_router(health_router)

    uvicorn.run(app, host="0.0.0.0", port=8081)


if __name__ == "__main__":
    main()
