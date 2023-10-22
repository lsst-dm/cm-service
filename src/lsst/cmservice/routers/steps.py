from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models

router = APIRouter(
    prefix="/steps",
    tags=["Steps"],
)


@router.get(
    "",
    response_model=list[models.Step],
    summary="List steps",
)
async def get_steps(
    campaign: int | None = None,
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db.Step]:
    q = select(db.Step)
    if campaign is not None:
        q = q.where(db.Step.campaign == campaign)
    q = q.offset(skip).limit(limit)
    async with session.begin():
        results = await session.scalars(q)
        return results.all()


@router.get(
    "/{step_id}",
    response_model=models.Step,
    summary="Retrieve a step",
)
async def read_step(
    step_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Step:
    async with session.begin():
        result = await session.get(db.Step, step_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Step not found")
        return result


@router.post(
    "",
    status_code=201,
    response_model=models.Step,
    summary="Create a step",
)
async def post_step(
    step_create: models.StepCreate,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Step:
    try:
        async with session.begin():
            step = db.Step(**step_create.dict())
            session.add(step)
        await session.refresh(step)
        return step
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e


@router.delete(
    "/{step_id}",
    status_code=204,
    summary="Delete a step",
)
async def delete_step(
    step_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> None:
    async with session.begin():
        step = await session.get(db.Step, step_id)
        if step is not None:
            await session.delete(step)


@router.put(
    "/{step_id}",
    response_model=models.Step,
    summary="Update a step",
)
async def update_production(
    step_id: int,
    step_update: models.Step,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Step:
    if step_update.id != step_id:
        raise HTTPException(status_code=400, detail="ID mismatch between URL and body")
    try:
        async with session.begin():
            step = await session.get(db.Step, step_id)
            if step is None:
                raise HTTPException(status_code=404, detail="Step not found")
            for var, value in vars(step_update).items():
                setattr(step, var, value)
        await session.refresh(step)
        return step
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e
