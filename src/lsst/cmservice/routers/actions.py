from fastapi import APIRouter, Depends, HTTPException
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
    """Invoke the interface.process_script function"""
    params = query.model_dump()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    try:
        return await interface.process_script(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.process_job function"""
    params = query.model_dump()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    try:
        return await interface.process_job(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.process_element function"""
    params = query.model_dump()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    try:
        return await interface.process_element(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.process function"""
    params = query.model_dump()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    try:
        return await interface.process(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.reset_script function"""
    params = query.model_dump()
    try:
        return await interface.reset_script(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.retry_script function"""
    params = query.model_dump()
    try:
        return await interface.retry_script(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.rescue_job function"""
    params = query.model_dump()
    try:
        return await interface.rescue_job(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.mark_job_rescued function"""
    params = query.model_dump()
    try:
        return await interface.mark_job_rescued(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


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
    """Invoke the interface.match_pipetask_errors function"""
    params = query.model_dump()
    try:
        return await interface.match_pipetask_errors(session, **params)
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
