from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..handlers import interface

router = APIRouter(
    prefix="/load",
    tags=["Loaders"],
)


@router.post(
    "/specification",
    status_code=201,
    response_model=models.Specification,
    summary="Load a Specification from a yaml file",
)
async def load_specification(
    query: models.SpecificationLoad,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Specification:
    """Load a specification object fom a yaml file

    Parameters
    ----------
    query: models.SpecificationLoad
        Details of what to load

    session: async_scoped_session
        DB session manager

    Returns
    -------
    specification: db.Specification
        Specification in question
    """
    try:
        result = await interface.load_specification(session, **query.model_dump())
        await session.commit()
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    return result


@router.post(
    "/campaign",
    status_code=201,
    response_model=models.Campaign,
    summary="Load a Specification and use it to create a `Campaign`",
)
async def load_and_create_campaign(
    query: models.LoadAndCreateCampaign,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    """Load a specification and use it to create a `Campaign`

    Parameters
    ----------
    query: models.LoadAndCreateCampaign
        Details of what to load and create

    session: async_scoped_session
        DB session manager

    Returns
    -------
    campaign: db.Campaign
        Campaign in question
    """
    try:
        result = await interface.load_and_create_campaign(session, **query.model_dump())
        await session.commit()
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    return result


@router.post(
    "/error_types",
    status_code=201,
    response_model=list[models.PipetaskErrorType],
    summary="Load a set of `PipetaskErrorType`s from a yaml file",
)
async def load_error_types(
    query: models.YamlFileQuery,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.PipetaskErrorType]:
    """Load a set of PipetaskErrorType object from a yaml file

    Parameters
    ----------
    query: models.YamlFileQuery
        Details of what to load

    session: async_scoped_session
        DB session manager

    Returns
    -------
    error_types : list[db.PipetaskErrorType]
        Newly loaded PipetaskErrorTypes
    """
    try:
        return await interface.load_error_types(session, **query.model_dump())
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg


@router.post(
    "/manifest_report",
    status_code=201,
    response_model=models.Job,
    summary="Load a manifest report yaml file",
)
async def load_manifest_report(
    query: models.LoadManifestReport,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Job:
    """Load a pipetask report and associated it to a Job

    Parameters
    ----------
    query: models.LoadManifestReport
        Details of what to load

    session: async_scoped_session
        DB session manager

    Returns
    -------
    job : Job
        Associated job
    """
    try:
        return await interface.load_manifest_report(session, **query.model_dump())
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
