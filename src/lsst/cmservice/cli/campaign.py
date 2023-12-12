from .. import db
from . import wrappers
from .commands import campaign_group

cli_group = campaign_group
db_class = db.Campaign

group_command = cli_group.command
sub_client = db_class.class_string


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


get_rows = wrappers.get_list_command(group_command, sub_client, db_class)

create = wrappers.get_create_command(group_command, sub_client, db_class)

delete = wrappers.get_delete_command(group_command, sub_client)

get_row = wrappers.get_row_command(get_command, sub_client, db_class)

get_spec_block = wrappers.get_spec_block_command(get_command, sub_client, db_class)

get_specification = wrappers.get_specification_command(get_command, sub_client, db_class)

get_resolved_collections = wrappers.get_resolved_collections_command(get_command, sub_client, db_class)

get_collections = wrappers.get_collections_command(get_command, sub_client, db_class)

get_child_config = wrappers.get_child_config_command(get_command, sub_client, db_class)

get_data_dict = wrappers.get_data_dict_command(get_command, sub_client, db_class)

get_spec_aliases = wrappers.get_spec_aliases_command(get_command, sub_client, db_class)

update_row = wrappers.get_update_command(update_command, sub_client, db_class)

update_status = wrappers.get_update_status_command(update_command, sub_client, db_class)

update_collections = wrappers.get_update_collections_command(update_command, sub_client, db_class)

update_child_config = wrappers.get_update_child_config_command(update_command, sub_client, db_class)

update_data_dict = wrappers.get_update_data_dict_command(update_command, sub_client, db_class)

update_spec_aliases = wrappers.get_update_spec_aliases_command(update_command, sub_client, db_class)

action_process = wrappers.get_action_process_command(action_command, sub_client, db_class)

action_run_check = wrappers.get_action_run_check_command(action_command, sub_client, db_class)

action_accept = wrappers.get_action_accept_command(action_command, sub_client, db_class)

action_reject = wrappers.get_action_reject_command(action_command, sub_client, db_class)

action_reset = wrappers.get_action_reset_command(action_command, sub_client, db_class)
