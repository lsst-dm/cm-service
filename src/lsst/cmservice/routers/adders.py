from fastapi import APIRouter, Depends
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
    result = await interface.add_groups(session, **query.dict())
    return result


@router.post(
    "/steps",
    status_code=201,
    response_model=models.Campaign,
    summary="Add Steps to a Campaign",
)
async def add_steps(
    query: models.AddGroups,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    result = await interface.add_steps(session, **query.dict())
    return result


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
    result = await interface.create_campaign(session, **query.dict())
    return result
