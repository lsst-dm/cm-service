"""http routers for managing Queue tables"""
from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.errors import CMMissingIDError
from .. import db, models
from . import wrappers

# Template specialization
# Specify the pydantic model for the table
ResponseModelClass = models.Queue
# Specify the pydantic model from making new rows
CreateModelClass = models.QueueCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.QueueUpdate
# Specify the associated database table
DbClass = db.Queue
# Specify the tag in the router documentation
TAG_STRING = "Queues"


# Build the router
router = APIRouter(
    prefix=f"/{DbClass.class_string}",
    tags=[TAG_STRING],
)


# Attach functions to the router
get_rows = wrappers.get_rows_function(router, ResponseModelClass, DbClass)
get_row = wrappers.get_row_function(router, ResponseModelClass, DbClass)
post_row = wrappers.post_row_function(
    router,
    ResponseModelClass,
    CreateModelClass,
    DbClass,
)
delete_row = wrappers.delete_row_function(router, DbClass)
update_row = wrappers.put_row_function(router, ResponseModelClass, UpdateModelClass, DbClass)


@router.get(
    "/process/{row_id}",
    response_model=bool,
    summary="Process the associated element",
)
async def process_element(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> bool:
    """Process associated element

    Parameters
    ----------
    row_id: int
        ID of the Queue row in question

    session: async_scoped_session
        DB session manager

    Returns
    -------
    can_continue: bool
        True if processing can continue
    """
    try:
        async with session.begin():
            queue = await db.Queue.get_row(session, row_id)
            can_continue = await queue.process_element(session)
    except CMMissingIDError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
    return can_continue


@router.get(
    "/sleep_time/{row_id}",
    response_model=int,
    summary="Check how long to sleep based on what is running",
)
async def sleep_time(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> int:
    """Check how long to sleep based on what is running

    Parameters
    ----------
    row_id: int
        ID of the Queue row in question

    session: async_scoped_session
        DB session manager

    Returns
    -------
    sleep_time: int
        Time to sleep before next call to process (in seconds)
    """
    try:
        async with session.begin():
            queue = await db.Queue.get_row(session, row_id)
            element_sleep_time = await queue.element_sleep_time(session)
    except CMMissingIDError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
    return element_sleep_time
