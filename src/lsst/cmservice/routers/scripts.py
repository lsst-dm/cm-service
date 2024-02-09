"""http routers for managing Script tables"""
from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common.enums import StatusEnum
from ..common.errors import CMMissingIDError
from . import wrappers

# Template specialization
# Specify the pydantic model for the table
ResponseModelClass = models.Script
# Specify the pydantic model from making new rows
CreateModelClass = models.ScriptCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.ScriptUpdate
# Specify the associated database table
DbClass = db.Script
# Specify the tag in the router documentation
TAG_STRING = "Scripts"


# Build the router
router = APIRouter(
    prefix=f"/{DbClass.class_string}",
    tags=[TAG_STRING],
)


# Attach functions to the router
get_rows = wrappers.get_rows_no_parent_function(router, ResponseModelClass, DbClass)
get_row = wrappers.get_row_function(router, ResponseModelClass, DbClass)
post_row = wrappers.post_row_function(
    router,
    ResponseModelClass,
    CreateModelClass,
    DbClass,
)
delete_row = wrappers.delete_row_function(router, DbClass)
update_row = wrappers.put_row_function(router, ResponseModelClass, UpdateModelClass, DbClass)
get_spec_block = wrappers.get_node_spec_block_function(router, DbClass)
get_specification = wrappers.get_node_specification_function(router, DbClass)
get_parent = wrappers.get_node_parent_function(router, models.Production, DbClass)
get_resolved_collections = wrappers.get_node_resolved_collections_function(router, DbClass)
get_collections = wrappers.get_node_collections_function(router, DbClass)
get_child_config = wrappers.get_node_child_config_function(router, DbClass)
get_data_dict = wrappers.get_node_data_dict_function(router, DbClass)
get_spec_aliases = wrappers.get_node_spec_aliases_function(router, DbClass)
update_status = wrappers.update_node_status_function(router, ResponseModelClass, DbClass)
update_collections = wrappers.update_node_collections_function(
    router,
    ResponseModelClass,
    DbClass,
)
update_child_config = wrappers.update_node_child_config_function(
    router,
    ResponseModelClass,
    DbClass,
)
update_data_dict = wrappers.update_node_data_dict_function(
    router,
    ResponseModelClass,
    DbClass,
)
update_spec_aliases = wrappers.update_node_spec_aliases_function(
    router,
    ResponseModelClass,
    DbClass,
)
accept = wrappers.get_node_accept_function(router, ResponseModelClass, DbClass)
reject = wrappers.get_node_reject_function(router, ResponseModelClass, DbClass)
reset = wrappers.get_node_reset_function(router, ResponseModelClass, DbClass)
process = wrappers.get_node_process_function(router, DbClass)
run_check = wrappers.get_node_run_check_function(router, DbClass)


@router.put(
    "/action/{row_id}/reset_script",
    response_model=StatusEnum,
    summary=f"Reset the status of a {DbClass.class_string}",
)
async def reset_script(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
    to_status: StatusEnum = StatusEnum.waiting,
) -> StatusEnum:
    """Reset a script to an earlier status

    Parameters
    ----------
    row_id: int
        ID of the script in question

    session: async_scoped_session
        DB session manager

    to_status: StatusEnum
        Status to set script to

    Returns
    -------
    new_status: StatusEnum
        New status of script
    """
    try:
        async with session.begin():
            script = await DbClass.get_row(session, row_id)
            result = await script.reset_script(session, to_status=to_status)
    except CMMissingIDError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
    return result


@router.put(
    "/action/{row_id}/copy",
    response_model=models.Script,
    summary=f"Make a copy of a {DbClass.class_string}",
)
async def copy(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Script:
    """Create and return a cope of a script

    Parameters
    ----------
    row_id: int
        ID of the script in question

    session: async_scoped_session
        DB session manager

    Returns
    -------
    new_script: Script
        Newly copied Script
    """
    try:
        async with session.begin():
            script = await DbClass.get_row(session, row_id)
            result = await script.copy_script(session)
    except CMMissingIDError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
    return result
