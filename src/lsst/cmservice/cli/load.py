import sys
from typing import Any

import click

from .. import db
from ..client.client import CMClient
from ..common.logging import LOGGER
from . import options
from .wrappers import output_pydantic_list, output_pydantic_object

logger = LOGGER.bind(module=__name__)


@click.group(name="load")
def load_group() -> None:
    """Read a yaml file and add stuff to the DB"""


@load_group.command()
@options.cmclient()
@options.output()
@options.yaml_file()
@options.namespace()
@options.allow_update()
def specification(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a Specification from a yaml file"""
    result = client.load.specification_cl(**kwargs)
    specifications = result.get("Specification", [])
    spec_blocks = result.get("SpecBlock", [])

    do_print = output not in [options.OutputEnum.json, options.OutputEnum.yaml]
    if do_print:
        print("Specifications: -----")
        output_pydantic_list(specifications, output, db.Specification.col_names_for_table)
    if do_print:
        print("SpecBlocks: -----")
        output_pydantic_list(spec_blocks, output, db.SpecBlock.col_names_for_table)


@load_group.command(name="campaign")
@options.cmclient()
@options.name()
@options.namespace()
@options.runtime_variable()
@options.output()
@options.campaign_yaml()
@options.yaml_file()
def campaign(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a Specification from a yaml file and make a Campaign"""
    try:
        result = client.load.campaign_cl(**kwargs)
        output_pydantic_object(result, output, db.Campaign.col_names_for_table)
    except RuntimeError as e:
        logger.error(e)
        sys.exit(1)
    except Exception:
        logger.exception()


@load_group.command()
@options.cmclient()
@options.output()
@options.yaml_file()
@options.allow_update()
def error_types(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load PipetaskErrorTypes from a yaml file"""
    result = client.load.error_types_cl(**kwargs)
    output_pydantic_list(result, output, db.PipetaskErrorType.col_names_for_table)


@load_group.command()
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
