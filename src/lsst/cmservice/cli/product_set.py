from .. import db
from . import wrappers
from .commands import product_set_group

cli_group = product_set_group
db_class = db.ProductSet

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
