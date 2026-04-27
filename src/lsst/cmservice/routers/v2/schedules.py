"""http routers for managing Schedule tables.

These routes are RESTful endpoints that deal with resources and collections of
resources.

These routes depend upon app-level exception handling for returning 422, 404,
and 409 errors, so specific handling of these cases is implemented only if some
custom behavior is needed.
"""

from collections.abc import Sequence
from typing import Annotated, cast
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
from pydantic import UUID4
from pydantic_extra_types.cron import CronStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, noload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.models.api.schedules import ScheduleConfiguration, ScheduleUpdate
from lsst.cmservice.models.db.schedules import (
    CreateManifestTemplate,
    CreateSchedule,
    ManifestTemplate,
    Schedule,
)
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
    # Do not eagerly load the relationship in this route
    statement = select(Schedule).options(noload(cast(InstrumentedAttribute, Schedule.templates)))

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
    response_model=Schedule,
    status_code=status.HTTP_200_OK,
)
@router.head(
    "/{schedule_name_or_id}",
    summary="Get header links for a specific schedule",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def read_schedule_resource(
    *,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_name_or_id: Annotated[str, Path()],
) -> Schedule | None:
    """Get a detail record for a specific Schedule by its name or ID.

    If the path parameter is a valid UUID, it will be used as an ID lookup,
    otherwise the schedule will be looked up by name. Although the ID is the
    primary key for the table, the name is also subject to a unique constraint.

    Notes
    -----
    The response model for this route will not include any relationship fields,
    like `templates`. Instead, consumers should dereference the "Templates" URL
    from the response header.
    """
    TemplatesT = cast(InstrumentedAttribute, Schedule.templates)

    try:
        schedule_id = UUID(schedule_name_or_id)
        schedule = await session.get_one(Schedule, schedule_id, options=[noload(TemplatesT)])
    except ValueError:
        statement = select(Schedule).options(noload(TemplatesT)).where(Schedule.name == schedule_name_or_id)
        schedule = (await session.exec(statement)).one()

    response.headers["Self"] = str(
        request.url_for("read_schedule_resource", schedule_name_or_id=str(schedule.id))
    )
    response.headers["Templates"] = str(
        request.url_for("read_schedule_template_collection", schedule_id=str(schedule.id))
    )

    if request.method == "HEAD":
        return None
    else:
        return schedule


@router.get(
    "/{schedule_id}/templates",
    summary="Get templates for a specific schedule",
)
async def read_schedule_template_collection(
    *,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_id: Annotated[UUID4, Path()],
) -> Sequence[ManifestTemplate]:
    """Get all manifest templates associated with a specific schedule id.

    It is not an error to request templates for a schedule id that does not
    exist; instead of a 404, this API will return an empty list.
    """

    statement = select(ManifestTemplate).where(ManifestTemplate.schedule_id == schedule_id)

    response.headers["Self"] = str(
        request.url_for("read_schedule_resource", schedule_name_or_id=str(schedule_id))
    )

    return (await session.exec(statement)).all()


@router.delete(
    "/{schedule_id}",
    summary="Delete schedule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_schedule_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_id: UUID,
) -> None:
    """Delete a schedule resource. The delete operation should cascade to any
    associated manifest template resources.
    """

    schedule = await session.get_one(Schedule, schedule_id)
    await session.delete(schedule)
    await session.commit()

    return None


@router.post(
    "/",
    summary="Create a new schedule",
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_manifest: CreateSchedule,
    schedule_owner: Annotated[str, Header(alias="X-Auth-Request-User")] = "root",
) -> None:
    """Create a schedule resource and its attached manifest templates.

    Notes
    -----
    - This route may return a 422 if any component of the `CreateSchedule` data
      does not successfully pass the model validator. This includes the
      presence of any invalid string values in a manifest template as found by
      a regex search.
    """

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

    if schedule.is_enabled:
        schedule.next_run_at = schedule.cron.next_run  # type: ignore[assignment]

    session.add(schedule)
    await session.commit()

    response.headers["Self"] = str(
        request.url_for("read_schedule_resource", schedule_name_or_id=str(schedule.id))
    )
    response.headers["Templates"] = str(
        request.url_for("read_schedule_template_collection", schedule_id=str(schedule.id))
    )


@router.put("/{schedule_id}", summary="Update a schedule")
@router.patch("/{schedule_id}", summary="Partial update for a schedule")
async def update_schedule_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_id: Annotated[str, Path()],
    schedule_update: ScheduleUpdate,
    schedule_owner: Annotated[str, Header(alias="X-Auth-Request-User")] = "root",
) -> None:
    """Completely or partially update an existing schedule resource and/or its
    attached manifest templates.
    """

    # FIXME this patch route doesn't successfully account for partial updates
    # to deeply nested models, e.g., adding or removing specific expressions.

    schedule = await session.get_one(Schedule, schedule_id)

    match request.method:
        case "PATCH":
            schedule_update.configuration = (
                ScheduleConfiguration(**schedule.configuration)
                .model_copy(update=schedule_update.configuration)
                .model_dump()
            )
            # Shallow update
            schedule.sqlmodel_update(schedule_update.model_dump(exclude_unset=True))
        case _:
            raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    if session.dirty:
        schedule.metadata_["mtime"] = element_time()
        schedule.metadata_["updated_by"] = schedule_owner

    if schedule.is_enabled:
        # TODO consider a custom validators? Might be overkill for this
        # The cron string is just a string when it comes back out of the db
        schedule_cron = CronStr(schedule.cron)
        schedule.next_run_at = schedule_cron.next_run  # type: ignore

    await session.commit()

    response.headers["Self"] = str(
        request.url_for("read_schedule_resource", schedule_name_or_id=str(schedule.id))
    )


@router.post(
    "/{schedule_id}/templates",
    summary="Add a single template to a Schedule",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
async def create_schedule_template_resource(
    *,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    schedule_id: Annotated[UUID4, Path()],
    template_manifest: CreateManifestTemplate,
) -> None:
    """Creates a new template record associated with a specific schedule."""
    # Create a new ManifestTemplate by applying the schedule ID to the incoming
    # model
    new_template = ManifestTemplate(
        **template_manifest.model_dump(exclude={"schedule_id", "id"}), schedule_id=schedule_id
    )

    # Auto-increment the version on conflict -- this is scalable to N versions
    # just by trying over and over, but at some point you need to put it on the
    # consumer that they should be incrementing the version in their post data
    # before hitting this API. This implementation tries to insert the "given"
    # version and n+1 as a courtesy, but does not try indefinitely.
    try:
        session.add(new_template)
        await session.commit()
    except IntegrityError:
        # Integrity Error (Duplicate)
        new_template.version += 1
        new_template.generate_id()
        await session.rollback()
        session.add(new_template)
    finally:
        # If this still fails, let it bubble up to the application exc handler
        await session.commit()

    response.headers["Templates"] = str(
        request.url_for("read_schedule_template_collection", schedule_id=schedule_id)
    )
