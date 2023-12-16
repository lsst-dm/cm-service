"""CLI to manage PipetaskError table"""

from .. import db
from . import options, wrappers
from .commands import pipetask_error_group

# Template specialization
# Specify the cli path to attach these commands to
cli_group = pipetask_error_group
# Specify the associated database table
db_class = db.PipetaskError
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.error_type_id(),
    options.task_id(),
    options.quanta(),
    options.diagnostic_message(),
    options.data_id(),
    options.output(),
]
# Specify the options for the update command
update_options = [
    options.cmclient(),
    options.error_type_id(),
    options.quanta(),
    options.diagnostic_message(),
    options.data_id(),
    options.output(),
]


# Construct derived templates
group_command = cli_group.command
sub_client = db_class.class_string


@cli_group.group()
def update() -> None:
    """Update an attribute"""


update_command = update.command


# Add functions to the router
get_rows = wrappers.get_list_command(group_command, sub_client, db_class)

create = wrappers.get_create_command(group_command, sub_client, db_class, create_options)

delete = wrappers.get_delete_command(group_command, sub_client)

get_row = wrappers.get_row_command(group_command, sub_client, db_class)

update_row = wrappers.get_update_command(update_command, sub_client, db_class, update_options)
