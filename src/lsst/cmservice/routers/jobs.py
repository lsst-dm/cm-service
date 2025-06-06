"""http routers for managing Job tables"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common.errors import CMBadStateTransitionError, CMMissingIDError
from ..common.logging import LOGGER
from ..handlers.functions import force_accept_node
from . import wrappers

logger = LOGGER.bind(module=__name__)

# Template specialization
# Specify the pydantic model for the table
ResponseModelClass = models.Job
# Specify the pydantic model from making new rows
CreateModelClass = models.JobCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.JobUpdate
# Specify the associated database table
DbClass = db.Job
# Specify the tag in the router documentation
TAG_STRING = "Jobs"


# Build the router
router = APIRouter(
    prefix=f"/{DbClass.class_string}",
    tags=[TAG_STRING],
)


# Attach functions to the router
get_rows = wrappers.get_rows_no_parent_function(router, ResponseModelClass, DbClass)
get_row = wrappers.get_row_function(router, ResponseModelClass, DbClass)
get_row_by_fullname = wrappers.get_row_by_fullname_function(router, ResponseModelClass, DbClass)
get_row_by_name = wrappers.get_row_by_name_function(router, ResponseModelClass, DbClass)
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
get_parent = wrappers.get_node_parent_function(router, models.Group, DbClass)
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
reject = wrappers.get_node_reject_function(router, ResponseModelClass, DbClass)
reset = wrappers.get_node_reset_function(router, ResponseModelClass, DbClass)
process = wrappers.get_node_process_function(router, DbClass)
run_check = wrappers.get_node_run_check_function(router, DbClass)

get_scripts = wrappers.get_element_get_scripts_function(router, DbClass)
get_all_scripts = wrappers.get_element_get_all_scripts_function(router, DbClass)
retry_script = wrappers.get_element_retry_script_function(router, DbClass)

get_wms_task_reports = wrappers.get_element_wms_task_reports_function(router, DbClass)
get_tasks = wrappers.get_element_tasks_function(router, DbClass)
get_products = wrappers.get_element_products_function(router, DbClass)


@router.get(
    "/get/{row_id}/errors",
    status_code=201,
    response_model=Sequence[models.PipetaskError],
    summary="Get the errors associated to a job",
)
async def get_errors(
    row_id: int,
    session: Annotated[async_scoped_session, Depends(db_session_dependency)],
) -> Sequence[db.PipetaskError]:
    try:
        async with session.begin():
            the_job = await DbClass.get_row(session, row_id)
            the_errors = await the_job.get_errors(session)
            return the_errors
    except CMMissingIDError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.post(
    "/action/{row_id}/accept",
    summary="Mark a Job as accepted",
    status_code=200,
    response_model=None,
)
async def accept_job(
    *,
    row_id: int,
    session: Annotated[async_scoped_session, Depends(db_session_dependency)],
    background_tasks: BackgroundTasks,
    force: bool = False,
    output_collection: str | None = None,
    response: Response,
) -> db.Job | None:
    """Put a job into an accepted state.

    If the force option is not supplied along with an output_collection, the
    action is dependent on CM State transition rules and may return a status
    422 if the accept action is not allowed.

    If the force option is set, the job's run collection is updated and all its
    (remaining) scripts are set to the accepted state irrespective of state
    transition rules. This is dispatched to a background task, and the status
    code 202 is returned.
    """
    if force:
        if output_collection is None:
            raise HTTPException(status_code=422, detail="Cannot force accept without output collection")
        background_tasks.add_task(
            force_accept_node, node=row_id, db_class=db.Job, output_collection=output_collection
        )
        response.status_code = 202
        return None
    else:
        # Standard element accept processing logic
        try:
            async with session.begin():
                the_node = await db.Job.get_row(session, row_id)
                ret_val = await the_node.accept(session)
            if TYPE_CHECKING:
                assert isinstance(ret_val, db.Job)
            return ret_val
        except CMMissingIDError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except CMBadStateTransitionError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except Exception as e:
            logger.error(e, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e
