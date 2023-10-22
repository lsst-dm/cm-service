from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models

router = APIRouter(
    prefix="/groups",
    tags=["Groups"],
)


@router.get(
    "",
    response_model=list[models.Group],
    summary="List groups",
)
async def get_groups(
    step: int | None = None,
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db.Group]:
    q = select(db.Group)
    if step is not None:
        q = q.where(db.Group.step == step)
    q = q.offset(skip).limit(limit)
    async with session.begin():
        results = await session.scalars(q)
        return results.all()


@router.get(
    "/{group_id}",
    response_model=models.Group,
    summary="Retrieve a group",
)
async def read_group(
    group_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Group:
    async with session.begin():
        result = await session.get(db.Group, group_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Group not found")
        return result


@router.post(
    "",
    status_code=201,
    response_model=models.Group,
    summary="Create a group",
)
async def post_group(
    group_create: models.GroupCreate,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Group:
    try:
        async with session.begin():
            group = db.Group(**group_create.dict())
            session.add(group)
        await session.refresh(group)
        return group
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e


@router.delete(
    "/{group_id}",
    status_code=204,
    summary="Delete a group",
)
async def delete_group(
    group_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> None:
    async with session.begin():
        group = await session.get(db.Group, group_id)
        if group is not None:
            await session.delete(group)


@router.put(
    "/{group_id}",
    response_model=models.Group,
    summary="Update a group",
)
async def update_production(
    group_id: int,
    group_update: models.Group,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Group:
    if group_update.id != group_id:
        raise HTTPException(status_code=400, detail="ID mismatch between URL and body")
    try:
        async with session.begin():
            group = await session.get(db.Group, group_id)
            if group is None:
                raise HTTPException(status_code=404, detail="Group not found")
            for var, value in vars(group_update).items():
                setattr(group, var, value)
        await session.refresh(group)
        return group
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e
