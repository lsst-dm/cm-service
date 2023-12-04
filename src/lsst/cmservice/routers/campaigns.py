from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models

response_model_class = models.Campaign
create_model_class = models.CampaignCreate
db_class = db.Campaign
class_string = "campaign"
tag_string = "Campaigns"

router = APIRouter(
    prefix=f"/{class_string}s",
    tags=[tag_string],
)


@router.get(
    "",
    response_model=list[response_model_class],
    summary=f"List {class_string}s",
)
async def get_rows(
    parent_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db_class]:
    return await db_class.get_rows(
        session,
        parent_id=parent_id,
        skip=skip,
        limit=limit,
        parent_class=db.Production,
    )


@router.get(
    "/{row_id}",
    response_model=response_model_class,
    summary=f"Retrieve a {class_string}",
)
async def get_row(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db_class:
    return await db_class.get_row(session, row_id)


@router.post(
    "",
    status_code=201,
    response_model=response_model_class,
    summary=f"Create a {class_string}",
)
async def post_row(
    row_create: create_model_class,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db_class:
    result = await db_class.create_row(session, **row_create.dict())
    await session.commit()
    return result


@router.delete(
    "/{row_id}",
    status_code=204,
    summary=f"Delete a {class_string}",
)
async def delete_row(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> None:
    await db_class.delete_row(session, row_id)


@router.put(
    "/{row_id}",
    response_model=response_model_class,
    summary=f"Update a {class_string}",
)
async def update_row(
    row_id: int,
    row_update: response_model_class,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db_class:
    result = await db_class.update_row(session, row_id, **row_update.dict())
    await session.commit()
    return result


@router.put(
    "/process/{campaign_id}",
    response_model=models.Campaign,
    summary="Process a campaign",
)
async def process_campaign(
    campaign_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Campaign:
    try:
        campaign = await db.Campaign.get_row(session, campaign_id)
        await campaign.process(session)
        return campaign
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e
