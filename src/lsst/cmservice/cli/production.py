"""CLI to manage Production table"""

from .. import db
from . import options, wrappers
from .commands import client_top


@client_top.group(name="production")
def production_group() -> None:
    """Manage production table"""


# Template specialization
# Specify the cli path to attach these commands to
cli_group = production_group
# Specify the associated database table
DbClass = db.Production
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.name(),
    options.output(),
]

# Construct derived templates
group_command = cli_group.command
sub_client = DbClass.class_string


# Add functions to the router
get_rows = wrappers.get_list_command(group_command, sub_client, DbClass)

create = wrappers.get_create_command(group_command, sub_client, DbClass, create_options)

delete = wrappers.get_delete_command(group_command, sub_client)

get_row = wrappers.get_row_command(group_command, sub_client, DbClass)
