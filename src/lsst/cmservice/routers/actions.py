from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from .. import db, models
from ..common.enums import StatusEnum
from ..common.types import AnyAsyncSession
from ..db.session import db_session_dependency
from ..handlers import interface

router = APIRouter(
    prefix="/actions",
    tags=["Actions"],
)


@router.post(
    "/process",
    status_code=201,
    summary="Process a Node",
)
async def process(
    query: models.ProcessNodeQuery,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> tuple[bool, StatusEnum]:
    """Invoke the interface.process function"""
    params = query.model_dump()
    if params.get("fake_status"):
        params["fake_status"] = StatusEnum(params["fake_status"])
    try:
        async with session.begin():
            ret_val = await interface.process(session, **params)
        return ret_val
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/reset_script",
    status_code=201,
    response_model=models.Script,
    summary="Reset `Script`",
)
async def reset_script(
    query: models.ResetScriptQuery,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> db.Script:
    """Invoke the interface.reset_script function"""
    params = query.model_dump()
    try:
        async with session.begin():
            ret_val = await interface.reset_script(session, **params)
        return ret_val
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/rescue_job",
    status_code=201,
    response_model=models.Job,
    summary="Run a resuce on a `Job`",
)
async def rescue_job(
    query: models.NodeQuery,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> db.Job:
    """Invoke the interface.rescue_job function"""
    params = query.model_dump()
    try:
        async with session.begin():
            ret_val = await interface.rescue_job(session, **params)
        return ret_val
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/mark_job_rescued",
    status_code=201,
    response_model=list[models.Job],
    summary="Mark a `Job` as rescued",
)
async def mark_job_rescued(
    query: models.NodeQuery,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> list[db.Job]:
    """Invoke the interface.mark_job_rescued function"""
    params = query.model_dump()
    try:
        async with session.begin():
            ret_val = await interface.mark_job_rescued(session, **params)
        return ret_val
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/rematch_errors",
    status_code=201,
    response_model=list[models.PipetaskError],
    summary="Rematch the Pipetask errors",
)
async def rematch_pipetask_errors(
    query: models.RematchQuery,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> list[db.PipetaskError]:
    """Invoke the interface.match_pipetask_errors function"""
    params = query.model_dump()
    try:
        async with session.begin():
            ret_val = await interface.match_pipetask_errors(session, **params)
        return ret_val
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
