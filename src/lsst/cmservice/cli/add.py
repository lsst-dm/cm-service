from .. import db
from ..client.client import CMClient
from . import options
from .commands import add
from .wrappers import output_pydantic_list


@add.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.child_configs()
def groups(
    client: CMClient,
    fullname: options.PartialOption,
    child_configs: dict,
    output: options.OutputEnum | None,
) -> None:
    """Add Groups to a Step"""
    result = client.add.groups(
        fullname=fullname,
        child_configs=child_configs,
    )
    output_pydantic_list(result, output, db.Group.col_names_for_table)


@add.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.child_configs()
def steps(
    client: CMClient,
    fullname: options.PartialOption,
    child_configs: dict,
    output: options.OutputEnum | None,
) -> None:
    """Add Steps to a Campaign"""
    result = client.add.steps(
        fullname=fullname,
        child_configs=child_configs,
    )
    output_pydantic_list(result, output, db.Step.col_names_for_table)
