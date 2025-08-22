from asyncio import Task
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from lsst.cmservice.core.config import config

from .. import __version__

health_router = APIRouter()
"""An API Router for a health endpoint"""


@health_router.get(
    "/healthz",
    description=("Return health information about the running application and its tasks, if any."),
    include_in_schema=True,
    response_model=dict[str, Any],
    tags=["internal", "health"],
)
async def get_healthz(request: Request) -> dict:
    """A healthz route for application health or liveliness checking.

    For any tasks running in the event loop and registered in the FastAPI app's
    state, check whether that task is still running; return a 500 along with
    relevant exception information if the task has ended.
    """
    server_ok = True
    healthz_response: dict[str, Any] = dict(name=config.asgi.title, version=__version__)

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
