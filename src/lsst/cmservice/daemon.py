from asyncio import Task, create_task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import structlog
import uvicorn
from anyio import sleep_until
from fastapi import APIRouter, FastAPI, HTTPException, Request
from safir.database import create_async_session, create_database_engine

from . import __version__
from .common.daemon import daemon_iteration
from .config import config

health_router = APIRouter()
"""An API Router for a health endpoint"""


@health_router.get("/healthz", tags=["internal", "health"])
async def get_healthz(request: Request) -> dict:
    """A healthz route for application health or liveliness checking.

    For any tasks running in the event loop and registered in the FastAPI app's
    state, check whether that task is still running; return a 500 along with
    relevant exception information if the task has ended.
    """
    server_ok = True
    healthz_response = {}

    task: Task
    for task in request.app.state.tasks:
        task_response: dict[str, bool | str | None] = {"task_running": True, "task_exception": None}
        if task.done():
            server_ok = False
            task_response["task_running"] = False
            task_response["task_exception"] = str(task.exception())
        healthz_response[task.get_name()] = task_response

    if not server_ok:
        raise HTTPException(status_code=500, detail=healthz_response)
    else:
        return healthz_response


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
    logger = structlog.get_logger(__name__)
    engine = create_database_engine(config.db.url, config.db.password)

    startup_time = datetime.now(UTC)
    sleep_time = timedelta(seconds=config.daemon.iteration_duration)

    async with engine.begin():
        session = await create_async_session(engine, logger)
        logger.info("Daemon starting.")
        _iteration_count = 0

        while True:
            _iteration_count += 1
            logger.info("Daemon starting iteration.")
            await daemon_iteration(session)
            logger.info(f"Daemon completed {_iteration_count} iterations.")
            _next_wakeup = startup_time + (sleep_time * _iteration_count)
            await sleep_until(_next_wakeup.timestamp())


def main() -> None:
    app = FastAPI(
        lifespan=lifespan,
        version=__version__,
    )

    app.include_router(health_router)

    uvicorn.run(app, host=config.asgi.host, port=config.asgi.port)


if __name__ == "__main__":
    main()
