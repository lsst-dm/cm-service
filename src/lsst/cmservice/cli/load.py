from typing import Any

from .. import db
from ..client.client import CMClient
from . import options
from .commands import load
from .wrappers import output_pydantic_list, output_pydantic_object


@load.command()
@options.cmclient()
@options.output()
@options.spec_name()
@options.yaml_file()
def specification(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a Specification from a yaml file"""
    result = client.load.specification(**kwargs)
    output_pydantic_object(result, output, db.Specification.col_names_for_table)


@load.command(name="campaign")
@options.cmclient()
@options.output()
@options.yaml_file()
@options.name()
@options.parent_name()
@options.spec_name()
@options.spec_block_name()
@options.handler()
@options.data()
@options.child_config()
@options.collections()
@options.spec_aliases()
def campaign(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a Specification from a yaml file and make a Campaign"""
    result = client.load.campaign(**kwargs)
    output_pydantic_object(result, output, db.Campaign.col_names_for_table)


@load.command()
@options.cmclient()
@options.output()
@options.yaml_file()
def error_types(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load PipetaskErrorTypes from a yaml file"""
    result = client.load.error_types(**kwargs)
    output_pydantic_list(result, output, db.PipetaskErrorType.col_names_for_table)


@load.command()
@options.cmclient()
@options.output()
@options.fullname()
@options.yaml_file()
def manifest_report(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a manifest report from a yaml file"""
    result = client.load.manifest_report(**kwargs)
    output_pydantic_object(result, output, db.Job.col_names_for_table)
