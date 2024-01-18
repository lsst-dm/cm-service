"""CLI to manage Queue table"""
from .. import db
from ..client.client import CMClient
from . import options, wrappers
from .commands import queue_group

# Template specialization
# Specify the cli path to attach these commands to
cli_group = queue_group
# Specify the associated database table
db_class = db.Queue
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.fullname(),
    options.interval(),
    options.output(),
]

# Construct derived templates
group_command = cli_group.command
sub_client = db_class.class_string


# Add functions to the router
get_rows = wrappers.get_list_command(group_command, sub_client, db_class)

create = wrappers.get_create_command(group_command, sub_client, db_class, create_options)

delete = wrappers.get_delete_command(group_command, sub_client)

get_row = wrappers.get_row_command(group_command, sub_client, db_class)


@queue_group.command(name="daemon")
@options.cmclient()
@options.row_id()
def daemon(
    client: CMClient,
    row_id: int,
) -> None:
    """Update a production"""
    client.queue.daemon(row_id)
