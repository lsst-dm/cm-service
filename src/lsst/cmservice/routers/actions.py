from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common.enums import StatusEnum
from ..handlers import interface

router = APIRouter(
    prefix="/actions",
    tags=["Actions"],
)


@router.post(
    "/process_script",
    status_code=201,
    response_model=tuple[bool, StatusEnum],
    summary="Process a script",
)
async def process_script(
    query: models.ProcessQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> tuple[bool, StatusEnum]:
    params = query.dict()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    return await interface.process_script(session, **params)


@router.post(
    "/process_job",
    status_code=201,
    response_model=tuple[bool, StatusEnum],
    summary="Process a job",
)
async def process_job(
    query: models.ProcessQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> tuple[bool, StatusEnum]:
    params = query.dict()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    return await interface.process_job(session, **params)


@router.post(
    "/process_element",
    status_code=201,
    response_model=tuple[bool, StatusEnum],
    summary="Process an Element",
)
async def process_element(
    query: models.ProcessQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> tuple[bool, StatusEnum]:
    params = query.dict()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    return await interface.process_element(session, **params)


@router.post(
    "/process",
    status_code=201,
    response_model=tuple[bool, StatusEnum],
    summary="Process a Node",
)
async def process(
    query: models.ProcessNodeQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> tuple[bool, StatusEnum]:
    params = query.dict()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    return await interface.process(session, **params)


@router.post(
    "/reset_script",
    status_code=201,
    response_model=models.Script,
    summary="Reset `Script`",
)
async def reset_script(
    query: models.UpdateStatusQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Script:
    params = query.dict()
    return await interface.reset_script(session, **params)


@router.post(
    "/retry_script",
    status_code=201,
    response_model=models.Script,
    summary="Run a retry on a `Script`",
)
async def retry_script(
    query: models.ScriptQueryBase,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Script:
    params = query.dict()
    return await interface.retry_script(session, **params)


@router.post(
    "/rescue_job",
    status_code=201,
    response_model=models.Job,
    summary="Run a resuce on a `Job`",
)
async def rescue_job(
    query: models.NodeQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Job:
    params = query.dict()
    return await interface.rescue_job(session, **params)


@router.post(
    "/mark_script_rescued",
    status_code=201,
    response_model=list[models.Job],
    summary="Mark a `Job` as rescued",
)
async def mark_job_rescued(
    query: models.NodeQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.Job]:
    params = query.dict()
    return await interface.mark_job_rescued(session, **params)


@router.post(
    "/rematch_errors",
    status_code=201,
    response_model=list[models.PipetaskError],
    summary="Rematch the Pipetask errors",
)
async def rematch_pipetask_errors(
    query: models.RematchQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.PipetaskError]:
    params = query.dict()
    return await interface.match_pipetask_errors(session, **params)
