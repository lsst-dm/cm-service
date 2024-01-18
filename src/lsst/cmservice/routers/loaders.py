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
    try:
        result = await interface.load_specification(session, **query.dict())
        await session.commit()
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}")
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
    try:
        result = await interface.load_and_create_campaign(session, **query.dict())
        await session.commit()
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}")
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
    try:
        return await interface.load_error_types(session, **query.dict())
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}")


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
    try:
        return await interface.load_manifest_report(session, **query.dict())
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}")
