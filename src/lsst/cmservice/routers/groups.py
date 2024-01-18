"""http routers for managing Group tables"""
from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from . import wrappers

# Template specialization
# Specify the pydantic model for the table
response_model_class = models.Group
# Specify the pydantic model from making new rows
create_model_class = models.GroupCreate
# Specify the associated database table
db_class = db.Group
# Specify the tag in the router documentation
tag_string = "Groups"


# Build the router
router = APIRouter(
    prefix=f"/{db_class.class_string}",
    tags=[tag_string],
)


# Attach functions to the router
get_rows = wrappers.get_rows_function(router, response_model_class, db_class)
get_row = wrappers.get_row_function(router, response_model_class, db_class)
get_row_by_fullname = wrappers.get_row_function(router, response_model_class, db_class)
post_row = wrappers.post_row_function(
    router,
    response_model_class,
    create_model_class,
    db_class,
)
delete_row = wrappers.delete_row_function(router, db_class)
update_row = wrappers.put_row_function(router, response_model_class, db_class)
get_spec_block = wrappers.get_node_spec_block_function(router, db_class)
get_specification = wrappers.get_node_specification_function(router, db_class)
get_parent = wrappers.get_node_parent_function(router, models.Production, db_class)
get_resolved_collections = wrappers.get_node_resolved_collections_function(router, db_class)
get_collections = wrappers.get_node_collections_function(router, db_class)
get_child_config = wrappers.get_node_child_config_function(router, db_class)
get_data_dict = wrappers.get_node_data_dict_function(router, db_class)
get_spec_aliases = wrappers.get_node_spec_aliases_function(router, db_class)
update_status = wrappers.update_node_status_function(router, response_model_class, db_class)
update_collections = wrappers.update_node_collections_function(
    router,
    response_model_class,
    db_class,
)
update_child_config = wrappers.update_node_child_config_function(
    router,
    response_model_class,
    db_class,
)
update_data_dict = wrappers.update_node_data_dict_function(
    router,
    response_model_class,
    db_class,
)
update_spec_aliases = wrappers.update_node_spec_aliases_function(
    router,
    response_model_class,
    db_class,
)
accept = wrappers.get_node_accept_function(router, response_model_class, db_class)
reject = wrappers.get_node_reject_function(router, response_model_class, db_class)
reset = wrappers.get_node_reset_function(router, response_model_class, db_class)
process = wrappers.get_node_process_function(router, response_model_class, db_class)
run_check = wrappers.get_node_run_check_function(router, response_model_class, db_class)

get_scripts = wrappers.get_element_get_scripts_function(router, db_class)
get_all_scripts = wrappers.get_element_get_all_scripts_function(router, db_class)
get_jobs = wrappers.get_element_get_jobs_function(router, db_class)
retry_script = wrappers.get_element_retry_script_function(router, db_class)
estimate_sleep_time = wrappers.get_element_estimate_sleep_time_function(router, db_class)


@router.post(
    "/action/{row_id}/rescue_job",
    status_code=201,
    response_model=models.Job,
    summary="Rescue a job from this group",
)
async def resuce_job(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Job:
    the_group = await db_class.get_row(session, row_id)
    return await the_group.rescue_job(session)


@router.post(
    "/action/{row_id}/mark_rescued",
    status_code=201,
    response_model=list[models.Job],
    summary="Mark jobs as rescued",
)
async def mark_job_rescued(
    row_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.Job]:
    the_group = await db_class.get_row(session, row_id)
    return await the_group.mark_job_rescued(session)
