from typing import Sequence

from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models

response_model_class = models.Dependency
create_model_class = models.DependencyCreate
db_class = db.ScriptDependency
class_string = "script_dependency"
tag_string = "ScriptDependencies"


router = APIRouter(
    prefix="/script_dependencies",
    tags=[tag_string],
)


@router.get(
    "",
    response_model=list[response_model_class],
    summary="List dependencies",
)
async def get_rows(
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db_class]:
    result = await db_class.get_rows(session, skip=skip, limit=limit)
    return result


@router.get(
    "/{row_id}",
    response_model=response_model_class,
    summary=f"Retrieve a {class_string}",
)
async def get_row(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db_class:
    result = await db_class.get_row(session, row_id)
    return result


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
