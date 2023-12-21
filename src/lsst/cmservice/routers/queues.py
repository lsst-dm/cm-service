from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from . import wrappers

response_model_class = models.Queue
create_model_class = models.QueueCreate
db_class = db.Queue
class_string = "queue"
tag_string = "Queues"

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


@router.get(
    "/process/{row_id}",
    response_model=bool,
    summary="Process the associated element",
)
async def process_element(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> bool:
    queue = await db.Queue.get_row(session, row_id)
    can_continue = await queue.process_element(session)
    return can_continue
