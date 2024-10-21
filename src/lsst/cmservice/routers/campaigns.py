"""http routers for managing Campaign tables"""

from fastapi import APIRouter

from .. import db, models
from . import wrappers

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

get_scripts = wrappers.get_element_get_scripts_function(router, DbClass)
get_all_scripts = wrappers.get_element_get_all_scripts_function(router, DbClass)
get_jobs = wrappers.get_element_get_jobs_function(router, DbClass)
retry_script = wrappers.get_element_retry_script_function(router, DbClass)
estimate_sleep_time = wrappers.get_element_estimate_sleep_time_function(router, DbClass)

get_wms_task_reports = wrappers.get_element_wms_task_reports_function(router, DbClass)
get_tasks = wrappers.get_element_tasks_function(router, DbClass)
get_products = wrappers.get_element_products_function(router, DbClass)
