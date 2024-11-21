"""CLI to manage WmsTaskReport table"""

from .. import db
from . import options, wrappers
from .commands import client_top


@client_top.group(name="wms_task_report")
def wms_task_report_group() -> None:
    """Manage WmsTaskReport table"""


# Template specialization
# Specify the cli path to attach these commands to
cli_group = wms_task_report_group
# Specify the associated database table
DbClass = db.WmsTaskReport
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.name(),
    options.job_id(),
    options.output(),
]
# Specify the options for the update command
update_options = [
    options.cmclient(),
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
