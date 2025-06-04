"""http routers for managing Campaign tables"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common import timestamp
from ..common.logging import LOGGER
from ..handlers.functions import render_campaign_steps
from . import wrappers

logger = LOGGER.bind(module=__name__)


# Template specialization
# Specify the pydantic model for the table
ResponseModelClass = models.Campaign
# Specify the pydantic model from making new rows
CreateModelClass = models.CampaignCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.CampaignUpdate
# Specify the associated database table
DbClass = db.Campaign
# Specify the tag in the router documentation
TAG_STRING = "Campaigns"


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
delete_row = wrappers.delete_row_function(router, DbClass)
update_row = wrappers.put_row_function(router, ResponseModelClass, UpdateModelClass, DbClass)
get_spec_block = wrappers.get_node_spec_block_function(router, DbClass)
get_specification = wrappers.get_node_specification_function(router, DbClass)
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

get_scripts = wrappers.get_element_get_scripts_function(router, DbClass)
get_all_scripts = wrappers.get_element_get_all_scripts_function(router, DbClass)
get_jobs = wrappers.get_element_get_jobs_function(router, DbClass)
retry_script = wrappers.get_element_retry_script_function(router, DbClass)

get_wms_task_reports = wrappers.get_element_wms_task_reports_function(router, DbClass)
get_tasks = wrappers.get_element_tasks_function(router, DbClass)
get_products = wrappers.get_element_products_function(router, DbClass)


@router.post(
    "/create",
    status_code=201,
    response_model=models.Campaign,
    summary="Create a campaign and a queue",
)
async def post_row(
    row_create: models.CampaignCreate,
    session: Annotated[async_scoped_session, Depends(db_session_dependency)],
    background_tasks: BackgroundTasks,
) -> db.Campaign:
    try:
        async with session.begin():
            campaign = await db.Campaign.create_row(session, **row_create.model_dump())
            _ = await db.Queue.create_row(
                session,
                fullname=campaign.fullname,
                time_next_check=timestamp.utc_datetime(campaign.metadata_.get("start_after", 0)),
                active=False,
            )

        background_tasks.add_task(render_campaign_steps, campaign=campaign.id)
        return campaign
    except Exception as msg:
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=500, detail=str(msg)) from msg


@router.get(
    "/{row_id}/steps/graph",
    status_code=200,
    summary="Construct and return a Campaign's graph of steps",
)
async def get_step_graph(
    row_id: int,
    session: Annotated[async_scoped_session, Depends(db_session_dependency)],
) -> dict:
    # Determine the namespace UUID for the campaign
    campaign = await db.Campaign.get_row(session, row_id)
    campaign_data = await campaign.data_dict(session)
    if (campaign_namespace := campaign_data.get("namespace")) is None:
        campaign_namespace = ...

    # Fetch the *edges* for the campaign from the step_dependency table
    statement = select(db.StepDependency).filter_by(namespace=campaign_namespace)
    edges = (await session.scalars(statement)).all()

    # Organize the edges into a graph
    # where the directed edge is edge.prereq_id -> edge.depend_id

    # Return the graph as JSON in node-link format
    assert edges
    return {}


@router.get(
    "/{row_id}/scripts/graph",
    status_code=200,
    summary="Construct and return a Campaign's graph of scripts",
)
async def get_script_graph(
    row_id: int,
    session: Annotated[async_scoped_session, Depends(db_session_dependency)],
) -> dict:
    # Determine the namespace UUID for the campaign
    # Fetch the *edges* for the campaign from the script_dependency table
    # Organize the edges into a graph
    # Return the graph as JSON in node-link format
    return {}
