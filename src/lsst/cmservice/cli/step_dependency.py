"""CLI to manage Group table"""
from .. import db
from . import wrappers
from .commands import step_dependency_group

# Template specialization
# Specify the cli path to attach these commands to
cli_group = step_dependency_group
# Specify the associated database table
db_class = db.StepDependency

# Construct derived templates
group_command = cli_group.command
sub_client = db_class.class_string


# Add functions to the router
get_rows = wrappers.get_list_command(group_command, sub_client, db_class)

create = wrappers.get_create_command(group_command, sub_client, db_class)

delete = wrappers.get_delete_command(group_command, sub_client)

get_row = wrappers.get_row_command(group_command, sub_client, db_class)
