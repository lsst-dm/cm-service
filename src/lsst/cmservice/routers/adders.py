from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..handlers import interface

router = APIRouter(
    prefix="/add",
    tags=["Adders"],
)


@router.post(
    "/groups",
    status_code=201,
    response_model=models.Step,
    summary="Add Groups to a `Step`",
)
async def add_groups(
    query: models.AddGroups,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Step:
    try:
        return await interface.add_groups(session, **query.dict())
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}")


@router.post(
    "/steps",
    status_code=201,
    response_model=models.Campaign,
    summary="Add Steps to a Campaign",
)
async def add_steps(
    query: models.AddSteps,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    try:
        return await interface.add_steps(session, **query.dict())
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}")


@router.post(
    "/campaign",
    status_code=201,
    response_model=models.Campaign,
    summary="Create a campaign",
)
async def add_campaign(
    query: models.CampaignCreate,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    try:
        return await interface.create_campaign(session, **query.dict())
    except Exception as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}")
