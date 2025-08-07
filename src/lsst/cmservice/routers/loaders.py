from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from .. import db, models
from ..common.types import AnyAsyncSession
from ..db.session import db_session_dependency
from ..handlers import functions, interface

router = APIRouter(
    prefix="/load",
    tags=["loaders"],
)


@router.post(
    "/steps",
    status_code=201,
    response_model=models.Campaign,
    summary="Add Steps to a Campaign",
)
async def add_steps(
    query: models.AddSteps,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> db.Campaign:
    """Invoke the interface.add_steps function"""
    try:
        async with session.begin():
            ret_val = await interface.add_steps(session, **query.model_dump())
        return ret_val
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/specification",
    status_code=201,
    response_model=models.Specification,
    summary="Load a Specification from a yaml file",
)
async def load_specification(
    query: models.SpecificationLoad,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> db.Specification:
    """Load a specification object fom a yaml file

    Parameters
    ----------
    query: models.SpecificationLoad
        Details of what to load

    session: AnyAsyncSession
        DB session manager

    Returns
    -------
    specification: db.Specification
        Specification in question
    """
    try:
        async with session.begin():
            result = await functions.load_specification(session, **query.model_dump())
        return result
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/campaign",
    status_code=201,
    response_model=models.Campaign,
    summary="Load a Specification and use it to create a `Campaign`",
)
async def load_and_create_campaign(
    query: models.LoadAndCreateCampaign,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> db.Campaign:
    """Load a specification and use it to create a `Campaign`

    Parameters
    ----------
    query: models.LoadAndCreateCampaign
        Details of what to load and create

    session: AnyAsyncSession
        DB session manager

    Returns
    -------
    campaign: db.Campaign
        Campaign in question
    """
    try:
        async with session.begin():
            result = await interface.load_and_create_campaign(session, **query.model_dump())
        return result
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/error_types",
    status_code=201,
    response_model=list[models.PipetaskErrorType],
    summary="Load a set of `PipetaskErrorType`s from a yaml file",
)
async def load_error_types(
    query: models.YamlFileQuery,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> list[db.PipetaskErrorType]:
    """Load a set of PipetaskErrorType object from a yaml file

    Parameters
    ----------
    query: models.YamlFileQuery
        Details of what to load

    session: AnyAsyncSession
        DB session manager

    Returns
    -------
    error_types : list[db.PipetaskErrorType]
        Newly loaded PipetaskErrorTypes
    """
    try:
        async with session.begin():
            the_error_types = await interface.load_error_types(session, **query.model_dump())
        return the_error_types
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/manifest_report",
    status_code=201,
    response_model=models.Job,
    summary="Load a manifest report yaml file",
)
async def load_manifest_report(
    query: models.LoadManifestReport,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> db.Job:
    """Load a pipetask report and associated it to a Job

    Parameters
    ----------
    query: models.LoadManifestReport
        Details of what to load

    session: AnyAsyncSession
        DB session manager

    Returns
    -------
    job : Job
        Associated job
    """
    try:
        async with session.begin():
            the_job = await interface.load_manifest_report(session, **query.model_dump())
        return the_job
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
