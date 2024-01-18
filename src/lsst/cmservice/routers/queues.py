"""http routers for managing Queue tables"""
from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from . import wrappers

# Template specialization
# Specify the pydantic model for the table
response_model_class = models.Queue
# Specify the pydantic model from making new rows
create_model_class = models.QueueCreate
# Specify the associated database table
db_class = db.Queue
# Specify the tag in the router documentation
tag_string = "Queues"


# Build the router
router = APIRouter(
    prefix=f"/{db_class.class_string}",
    tags=[tag_string],
)


# Attach functions to the router
get_rows = wrappers.get_rows_function(router, response_model_class, db_class)
get_row = wrappers.get_row_function(router, response_model_class, db_class)
post_row = wrappers.post_row_function(
    router,
    response_model_class,
    create_model_class,
    db_class,
)
delete_row = wrappers.delete_row_function(router, db_class)
update_row = wrappers.put_row_function(router, response_model_class, db_class)


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


@router.get(
    "/sleep_time/{row_id}",
    response_model=int,
    summary="Process the associated element",
)
async def sleep_time(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> int:
    queue = await db.Queue.get_row(session, row_id)
    element_sleep_time = await queue.element_sleep_time(session)
    return element_sleep_time
