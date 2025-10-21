"""http routers for managing the Task table.

The /tasks endpoint supports a collection resource and single resources
representing task objects within CM-Service. Task objects are created and read
by the Daemon to affect a single transition within a Node's state machine.

There are no APIs for creating or editing Task resources.
"""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import UUID5
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.logging import LOGGER
from ...db.campaigns_v2 import Task
from ...db.session import db_session_dependency

logger = LOGGER.bind(module=__name__)

# Build the router
router = APIRouter(
    prefix="/tasks",
    tags=["tasks", "v2"],
)


@router.get(
    "/",
    summary="Get a list of Tasks",
)
async def read_task_collection(
    *,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
    campaign_id: Annotated[UUID5 | None, Query()] = None,
    node_id: Annotated[UUID5 | None, Query()] = None,
) -> Sequence[Task]:
    """A paginated API returning a list of all Tasks known to the
    application, from newest to oldest. Query parameters may scope the request
    to a specific campaign or node id. If both parameters are set, the campaign
    id is ignored.
    """
    try:
        statement = select(Task).order_by(col(Task.created_at).asc().nulls_last()).offset(offset).limit(limit)

        if node_id is not None:
            statement = statement.where(Task.node == node_id)
        elif campaign_id is not None:
            statement = statement.where(Task.namespace == campaign_id)

        tasks = await session.exec(statement)

        response.headers["Next"] = str(
            request.url_for("read_task_collection").include_query_params(offset=(offset + limit), limit=limit)
        )
        if offset > 0:
            response.headers["Previous"] = str(
                request.url_for("read_task_collection").include_query_params(
                    offset=(offset - limit), limit=limit
                )
            )
        return tasks.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{str(msg)}") from msg
