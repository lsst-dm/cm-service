from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models

router = APIRouter(
    prefix="/campaigns",
    tags=["Campaigns"],
)


@router.get(
    "",
    response_model=list[models.Campaign],
    summary="List campaigns",
)
async def get_campaigns(
    production: int | None = None,
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db.Campaign]:
    q = select(db.Campaign)
    if production is not None:
        q = q.where(db.Campaign.production == production)
    q = q.offset(skip).limit(limit)
    async with session.begin():
        results = await session.scalars(q)
        return results.all()


@router.get(
    "/{campaign_id}",
    response_model=models.Campaign,
    summary="Retrieve a campaign",
)
async def read_campaign(
    campaign_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    async with session.begin():
        result = await session.get(db.Campaign, campaign_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return result


@router.post(
    "",
    status_code=201,
    response_model=models.Campaign,
    summary="Create a campaign",
)
async def post_campaign(
    campaign_create: models.CampaignCreate,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    try:
        async with session.begin():
            campaign = db.Campaign(**campaign_create.dict())
            session.add(campaign)
        await session.refresh(campaign)
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e
    else:
        return campaign


@router.delete(
    "/{campaign_id}",
    status_code=204,
    summary="Delete a campaign",
)
async def delete_campaign(
    campaign_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> None:
    async with session.begin():
        campaign = await session.get(db.Campaign, campaign_id)
        if campaign is not None:
            await session.delete(campaign)


@router.put(
    "/{campaign_id}",
    response_model=models.Campaign,
    summary="Update a campaign",
)
async def update_production(
    campaign_id: int,
    campaign_update: models.Campaign,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    if campaign_update.id != campaign_id:
        raise HTTPException(status_code=400, detail="ID mismatch between URL and body")
    try:
        async with session.begin():
            campaign = await session.get(db.Campaign, campaign_id)
            if campaign is None:
                raise HTTPException(status_code=404, detail="Campaign not found")
            for var, value in vars(campaign_update).items():
                setattr(campaign, var, value)
        await session.refresh(campaign)
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e
    else:
        return campaign
