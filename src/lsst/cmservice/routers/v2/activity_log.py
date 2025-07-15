"""http routers for accessing the activity log."""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.logging import LOGGER
from ...db.campaigns_v2 import ActivityLog
from ...db.session import db_session_dependency

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/logs",
    tags=["logs", "v2"],
)


@router.get(
    "/",
    summary="Get a list of Activity Log entries",
)
async def read_activity_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
    node: Annotated[UUID | None, Query(description="ID of a Node")] = None,
    campaign: Annotated[UUID | None, Query(description="ID of a Campaign")] = None,
    pilot: Annotated[str | None, Query(description="String name of a pilot")] = None,
    since: Annotated[
        datetime | None, Query(description="Datetime of earliest log, in any format pydantic can validate")
    ] = None,
) -> Sequence[ActivityLog]:
    """A paginated API returning a list of all Activity Logs known to the
    application, with query parameters allowing some constraints.
    """
    statement = select(ActivityLog)

    # Add predicates for query parameters
    if node is not None:
        statement = statement.where(ActivityLog.node == node)
    if campaign is not None:
        statement = statement.where(ActivityLog.namespace == campaign)
    if pilot is not None:
        statement = statement.where(ActivityLog.operator == pilot)
    if since is not None:
        statement = statement.where(ActivityLog.finished_at >= since)  # type: ignore[operator]

    statement = statement.order_by(col(ActivityLog.created_at).desc()).offset(offset).limit(limit)
    activity_logs = (await session.exec(statement)).all()
    return activity_logs


@router.get(
    "/{activity_log_id}",
    summary="Get single activity log detail",
)
async def read_activity_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    activity_log_id: UUID,
) -> ActivityLog:
    """Fetch a single activity log from the database given the log's ID"""

    activity_log = await session.get(ActivityLog, activity_log_id)
    # set the response headers
    if activity_log is not None:
        response.headers["Campaign"] = str(
            request.url_for("read_campaign_resource", campaign_name_or_id=activity_log.namespace)
        )
        response.headers["Node"] = str(request.url_for("read_node_resource", node_name=activity_log.node))
        response.headers["Self"] = str(
            request.url_for("read_activity_resource", activity_log_id=activity_log_id)
        )
        return activity_log
    else:
        raise HTTPException(status_code=404)
