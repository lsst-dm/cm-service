"""http routers for accessing the audit log."""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.models.db.audit import AuditLog
from lsst.cmservice.models.enums import ManifestKind

from ...common.logging import LOGGER
from ...db.session import db_session_dependency
from ...parsing.json import coerce_json_value

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/audit",
    tags=["audit", "v2"],
)


@router.get(
    "/",
    summary="Get a list of Audit Log entries",
)
async def read_audit_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
    object: Annotated[UUID | None, Query(description="ID of an Object")] = None,
    object_type: Annotated[str | None, Query(description="Kind of Object")] = None,
    request_id: Annotated[UUID | None, Query(description="Request ID that triggered the audit entry")] = None,
    actor: Annotated[str | None, Query(description="String name of an actor")] = None,
    since: Annotated[
        datetime | None, Query(description="Datetime of earliest log, in any format pydantic can validate")
    ] = None,
    sort: Annotated[str, Query(description="Sort field(s); `-` prefix descending")] = "created_at",
) -> Sequence[AuditLog]:
    """A paginated API returning a list of all Audit Logs known to the
    application, with query parameters allowing some constraints. Arbitrary
    context predicates should be added as `?context.field=value`.
    """
    statement = select(AuditLog)

    # Add predicates for query parameters
    if object is not None:
        statement = statement.where(AuditLog.object_id == object)
    if object_type is not None:
        statement = statement.where(AuditLog.object_type == ManifestKind[object_type])
    if actor is not None:
        statement = statement.where(AuditLog.actor == actor)
    if request_id is not None:
        statement = statement.where(AuditLog.request_id == request_id)
    if since is not None:
        statement = statement.where(AuditLog.created_at >= since)

    # Add arbitrary context predicates
    context_params = {
        k.partition(".")[2]: coerce_json_value(v)
        for k, v in request.query_params.items()
        if k.startswith("context.")
    }
    if context_params:
        # produces a JSONB containment (`@>`) test
        statement = statement.where(col(AuditLog.context).contains(context_params))

    # Add predicates for sorting
    for field in sort.split(","):
        field = field.strip()
        column = col(getattr(AuditLog, field.removeprefix("-")))
        if field.startswith("-"):
            statement = statement.order_by(column.desc())
        else:
            statement = statement.order_by(column.asc())

    statement = statement.offset(offset).limit(limit)
    audit_logs = (await session.exec(statement)).all()
    return audit_logs
