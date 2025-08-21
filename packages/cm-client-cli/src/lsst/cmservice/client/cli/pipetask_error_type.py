"""CLI to manage PipetaskErrorType table"""

import click

from lsst.cmservice.core import db

from . import options, wrappers


@click.group(name="pipetask_error_type")
def pipetask_error_type_group() -> None:
    """Manage PipetaskErrorType table"""


# Template specialization
# Specify the cli path to attach these commands to
cli_group = pipetask_error_type_group
# Specify the associated database table
DbClass = db.PipetaskErrorType
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.error_action(),
    options.error_flavor(),
    options.error_source(),
    options.diagnostic_message(),
    options.task_name(),
    options.output(),
]
# Specify the options for the update command
update_options = [
    options.cmclient(),
    options.error_action(),
    options.error_flavor(),
    options.error_source(),
    options.diagnostic_message(),
    options.task_name(),
    options.output(),
]

# Construct derived templates
group_command = cli_group.command
sub_client = DbClass.class_string


@cli_group.group()
def update() -> None:
    """Update an attribute"""


update_command = update.command


# Add functions to the router
get_rows = wrappers.get_list_command(group_command, sub_client, DbClass)

create = wrappers.get_create_command(group_command, sub_client, DbClass, create_options)

delete = wrappers.get_delete_command(group_command, sub_client)

get_row = wrappers.get_row_command(group_command, sub_client, DbClass)

update_row = wrappers.get_update_command(update_command, sub_client, DbClass, update_options)
