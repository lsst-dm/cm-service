"""CLI to manage Job table"""
from .. import db
from . import options, wrappers
from .commands import job_group

# Template specialization
# Specify the cli path to attach these commands to
cli_group = job_group
DbClass = db.Job
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.name(),
    options.data(),
    options.child_config(),
    options.collections(),
    options.spec_aliases(),
    options.handler(),
    options.parent_name(),
    options.spec_name(),
    options.spec_block_name(),
    options.spec_block_assoc_name(),
    options.output(),
]
update_options = [
    options.cmclient(),
    options.row_id(),
    options.data(),
    options.child_config(),
    options.collections(),
    options.spec_aliases(),
    options.wms_job_id(),
    options.handler(),
    options.output(),
]

# Construct derived templates
group_command = cli_group.command
sub_client = DbClass.class_string


@cli_group.group()
def get() -> None:
    """Get an attribute"""


get_command = get.command


@cli_group.group()
def update() -> None:
    """Update an attribute"""


update_command = update.command


@cli_group.group()
def action() -> None:
    """Take an action"""


action_command = action.command


# Add functions to the router
get_rows = wrappers.get_list_command(group_command, sub_client, DbClass)

create = wrappers.get_create_command(group_command, sub_client, DbClass, create_options)

delete = wrappers.get_delete_command(group_command, sub_client)

get_row = wrappers.get_row_command(get_command, sub_client, DbClass)

get_spec_block = wrappers.get_spec_block_command(get_command, sub_client)

get_specification = wrappers.get_specification_command(get_command, sub_client)

get_resolved_collections = wrappers.get_resolved_collections_command(get_command, sub_client)

get_collections = wrappers.get_collections_command(get_command, sub_client)

get_child_config = wrappers.get_child_config_command(get_command, sub_client)

get_data_dict = wrappers.get_data_dict_command(get_command, sub_client)

get_spec_aliases = wrappers.get_spec_aliases_command(get_command, sub_client)

update_row = wrappers.get_update_command(update_command, sub_client, DbClass, update_options)

update_status = wrappers.get_update_status_command(update_command, sub_client, DbClass)

update_collections = wrappers.get_update_collections_command(update_command, sub_client)

update_child_config = wrappers.get_update_child_config_command(update_command, sub_client)

update_data_dict = wrappers.get_update_data_dict_command(update_command, sub_client)

update_spec_aliases = wrappers.get_update_spec_aliases_command(update_command, sub_client)

action_process = wrappers.get_action_process_command(action_command, sub_client)

action_run_check = wrappers.get_action_run_check_command(action_command, sub_client)

action_accept = wrappers.get_action_accept_command(action_command, sub_client, DbClass)

action_reject = wrappers.get_action_reject_command(action_command, sub_client, DbClass)

action_reset = wrappers.get_action_reset_command(action_command, sub_client, DbClass)

get_scripts = wrappers.get_element_scripts_command(get_command, sub_client)

get_all_scripts = wrappers.get_element_all_scripts_command(get_command, sub_client)

action_retry_script = wrappers.get_element_retry_script_command(action_command, sub_client)

get_sleep_time = wrappers.get_element_estimate_sleep_time_command(action_command, sub_client)

get_wms_task_reports = wrappers.get_element_wms_task_reports_command(get_command, sub_client)

get_tasks = wrappers.get_element_tasks_command(get_command, sub_client)

get_products = wrappers.get_element_products_command(get_command, sub_client)
