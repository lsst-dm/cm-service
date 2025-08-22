"""CLI to manage Queue table"""

import click

from lsst.cmservice.core import db

from ..client.client import CMClient
from . import options, wrappers


@click.group(name="queue")
def queue_group() -> None:
    """Manage the processing queue"""


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
    options.row_id(),
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
    """Update a queue"""
    client.queue.daemon(row_id)


@queue_group.command(name="pause")
@options.cmclient()
@options.row_id()
def pause(
    client: CMClient,
    row_id: int,
) -> None:
    """Pause a started queue"""
    client.queue.pause(row_id)


@queue_group.command(name="start")
@options.cmclient()
@options.row_id()
def start(
    client: CMClient,
    row_id: int,
) -> None:
    """Start a paused queue"""
    client.queue.start(row_id)
