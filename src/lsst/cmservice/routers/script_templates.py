from collections.abc import Sequence

from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models

response_model_class = models.ScriptTemplate
create_model_class = models.ScriptTemplateCreate
db_class = db.ScriptTemplate
class_string = "script_template"
tag_string = "ScriptTemplates"


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
    parent_name: str | None = None,
    skip: int = 0,
    limit: int = 100,
    session: async_scoped_session = Depends(db_session_dependency),
) -> Sequence[db_class]:
    return await db_class.get_rows(
        session,
        parent_id=parent_id,
        skip=skip,
        limit=limit,
        parent_name=parent_name,
        parent_class=db.Specification,
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
