from collections.abc import Sequence

from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common.enums import StatusEnum

response_model_class = models.Script
create_model_class = models.ScriptCreate
db_class = db.Script
class_string = "script"
tag_string = "Scripts"


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
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db_class]:
    return await db_class.get_rows(session, skip=skip, limit=limit)


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
    return await db_class.update_row(session, row_id, **row_update.dict())


@router.put(
    "/set_status/{row_id}/",
    response_model=response_model_class,
    summary=f"The the status of a {class_string}",
)
async def update_row_status(
    row_id: int,
    status: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db_class:
    result = await db_class.update_row(session, row_id, status=StatusEnum(status))
    await session.commit()
    return result
