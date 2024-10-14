"""CLI to manage Queue table"""

import click

from .. import db
from ..client.client import CMClient
from ..common.enums import LevelEnum
from . import options, wrappers
from .commands import queue_group

# Template specialization
# Specify the cli path to attach these commands to
cli_group = queue_group
# Specify the associated database table
DbClass = db.Queue
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.fullname(),
    options.interval(),
    options.output(),
]
# Specify the options for the update command
update_options = [
    options.cmclient(),
    options.fullname(),
    options.interval(),
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


@queue_group.command(name="daemon")
@options.cmclient()
@options.row_id()
def daemon(
    client: CMClient,
    row_id: int,
) -> None:
    """Update a production"""
    client.queue.daemon(row_id)


@queue_group.command(name="add")
@options.cmclient()
@options.fullname()
@options.row_id()
@options.element_level(required=True)
def add_entry(
    client: CMClient,
    *,
    fullname: str | None = None,
    row_id: int | None = None,
    element_level: LevelEnum,
) -> None:
    """Add an element to the queue."""

    if (fullname is None) and (row_id is None):
        raise click.UsageError("Must supply either fullname or row_id but not both.")

    client.queue.add_entry(element_level=element_level, fullname=fullname, row_id=row_id)
