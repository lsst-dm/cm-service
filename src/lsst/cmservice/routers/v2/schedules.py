"""http routers for managing Schedule tables."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.models.db.schedules import CreateScheduleModel, ManifestTemplate, Schedule
from lsst.cmservice.models.lib.timestamp import element_time

from ...common.logging import LOGGER
from ...db.session import db_session_dependency

logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/schedules",
    tags=["schedules", "templates", "v2"],
)


@router.get(
    "/",
    summary="Get a list of schedules",
)
async def read_schedule_collection(
    *,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    owner: Annotated[str | None, Query()] = None,
) -> Sequence[Schedule]:
    """A paginated API returning a list of all Schedules known to the
    application, ordered by their next scheduled runtime.
    """
    statement = select(Schedule)

    if owner is not None:
        statement = statement.where(Schedule.metadata_["owner"].astext == owner)

    statement = statement.offset(offset).limit(limit)

    schedules = await session.exec(statement)

    # Response header links
    response.headers["Next"] = str(request.url.include_query_params(offset=(offset + limit), limit=limit))

    if offset > 0:
        response.headers["Previous"] = str(
            request.url.include_query_params(offset=(offset - limit), limit=limit)
        )

    return schedules.all()


@router.get(
    "/{schedule_name_or_id}",
    summary="Get a specific schedule",
)
async def read_schedule_resource(
    *,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_name_or_id: Annotated[str, Path()],
) -> Schedule | None:
    """A paginated API returning a list of all Schedules known to the
    application, ordered by their next scheduled runtime.
    """

    try:
        schedule_id = UUID(schedule_name_or_id)
        schedule = await session.get(Schedule, schedule_id)
    except ValueError:
        statement = select(Schedule).where(Schedule.name == schedule_name_or_id)
        schedule = (await session.exec(statement)).one_or_none()

    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    response.headers["Self"] = str(
        request.url_for("read_schedule_resource", schedule_name_or_id=str(schedule.id))
    )

    return schedule


@router.delete(
    "/{schedule_id}",
    summary="Delete schedule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_name_or_id: UUID,
) -> None:
    """Delete a schedule resource. The delete operation should cascade to any
    associated manifest template resources.
    """
    ...


@router.post(
    "/",
    summary="Create a new schedule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def create_schedule_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_manifest: CreateScheduleModel,
    schedule_owner: Annotated[str, Header(alias="X-Auth-Request-User")] = "root",
) -> None:
    """Create a schedule resource and its attached manifest templates."""

    # Construct ORM objects for the schedule and its constituent templates
    schedule = Schedule(
        **schedule_manifest.model_dump(exclude={"metadata_", "templates"}),
        metadata_=schedule_manifest.metadata_
        | {
            "crtime": element_time(),
            "owner": schedule_owner,
        },
        templates=[
            ManifestTemplate(**template.model_dump(exclude_none=True), schedule_id=schedule_manifest.id)
            for template in schedule_manifest.templates
        ],
    )

    # Cleanup potential inappropriate fields from the manifest templates
    # - metadata.namespace (meaningless until created)
    # - any START/END nodes (meaningless for loading into new campaigns)

    if schedule.is_enabled:
        schedule.next_run_at = schedule.cron.next_run  # type: ignore[assignment]

    session.add(schedule)
    await session.commit()

    response.headers["Self"] = str(
        request.url_for("read_schedule_resource", schedule_name_or_id=str(schedule.id))
    )


# TODO: PUT = update a schedule resource (add/remove manifest templates)
