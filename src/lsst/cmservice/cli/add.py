from .. import db
from ..client.client import CMClient
from . import options
from .commands import add
from .wrappers import _output_pydantic_list, _output_pydantic_object


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
    _output_pydantic_list(result, output, db.Group.col_names_for_table)


@add.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.child_configs()
def steps_(
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
    _output_pydantic_list(result, output, db.Step.col_names_for_table)


@add.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.child_configs()
def campaign(
    client: CMClient,
    fullname: options.PartialOption,
    child_configs: dict,
    output: options.OutputEnum | None,
) -> None:
    """Add a Campaign"""
    result = client.add.campaign(
        fullname=fullname,
        **child_configs,
    )
    _output_pydantic_object(result, output, db.Campaign.col_names_for_table)
