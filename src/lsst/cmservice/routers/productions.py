from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models

router = APIRouter(
    prefix="/productions",
    tags=["Productions"],
)


@router.get(
    "",
    response_model=list[models.Production],
    summary="List productions",
)
async def get_productions(
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db.Production]:
    async with session.begin():
        results = await session.scalars(select(db.Production).offset(skip).limit(limit))
        return results.all()


@router.get(
    "/{production_id}",
    response_model=models.Production,
    summary="Retrieve a production",
)
async def get_production(
    production_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Production:
    async with session.begin():
        result = await session.get(db.Production, production_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Production not found")
        return result


@router.post(
    "",
    status_code=201,
    response_model=models.Production,
    summary="Create a production",
)
async def post_production(
    production_create: models.ProductionCreate,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Production:
    try:
        async with session.begin():
            production = db.Production(**production_create.dict())
            session.add(production)
        await session.refresh(production)
        return production
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e


@router.delete(
    "/{production_id}",
    status_code=204,
    summary="Delete a production",
)
async def delete_production(
    production_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> None:
    async with session.begin():
        production = await session.get(db.Production, production_id)
        if production is not None:
            await session.delete(production)


@router.put(
    "/{production_id}",
    response_model=models.Production,
    summary="Update a production",
)
async def update_production(
    production_id: int,
    production_update: models.Production,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Production:
    if production_update.id != production_id:
        raise HTTPException(status_code=400, detail="ID mismatch between URL and body")
    try:
        async with session.begin():
            production = await session.get(db.Production, production_id)
            if production is None:
                raise HTTPException(status_code=404, detail="Production not found")
            for var, value in vars(production_update).items():
                setattr(production, var, value)
        await session.refresh(production)
        return production
    except IntegrityError as e:
        raise HTTPException(422, detail=str(e)) from e
