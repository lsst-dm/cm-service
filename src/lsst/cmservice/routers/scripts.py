from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common.enums import StatusEnum
from . import wrappers

response_model_class = models.Script
create_model_class = models.ScriptCreate
db_class = db.Script
class_string = "script"
tag_string = "Scripts"


router = APIRouter(
    prefix=f"/{class_string}s",
    tags=[tag_string],
)


get_rows = wrappers.get_rows_function(router, response_model_class, db_class, class_string)
get_row = wrappers.get_row_function(router, response_model_class, db_class, class_string)
post_row = wrappers.post_row_function(
    router,
    response_model_class,
    create_model_class,
    db_class,
    class_string,
)
delete_row = wrappers.delete_row_function(router, db_class, class_string)
update_row = wrappers.put_row_function(router, response_model_class, db_class, class_string)


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
