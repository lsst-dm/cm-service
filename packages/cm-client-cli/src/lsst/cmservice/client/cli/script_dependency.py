"""CLI to manage ScriptDependency table"""

import click

from lsst.cmservice.core import db

from . import options, wrappers


@click.group(name="script_dependency")
def script_dependency_group() -> None:
    """Manage ScriptDependency table"""


# Template specialization
# Specify the cli path to attach these commands to
cli_group = script_dependency_group
# Specify the associated database table
DbClass = db.ScriptDependency
# Specify the options for the create command
create_options = [
    options.cmclient(),
    options.prereq_id(),
    options.depend_id(),
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
