from typing import Any

from .. import db
from ..client.client import CMClient
from . import options
from .commands import load
from .wrappers import output_pydantic_list, output_pydantic_object


@load.command()
@options.cmclient()
@options.output()
@options.yaml_file()
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
    script_templates = result.get("ScriptTemplate", [])

    do_print = output not in [options.OutputEnum.json, options.OutputEnum.yaml]
    if specifications:
        if do_print:
            print("Specifications: -----")
        output_pydantic_list(specifications, output, db.Specification.col_names_for_table)
    if spec_blocks:
        if do_print:
            print("SpecBlocks: -----")
        output_pydantic_list(spec_blocks, output, db.SpecBlock.col_names_for_table)
    if script_templates:
        if do_print:
            print("ScriptTemplates: -----")
        output_pydantic_list(script_templates, output, db.ScriptTemplate.col_names_for_table)


@load.command(name="campaign")
@options.cmclient()
@options.output()
@options.campaign_yaml()
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
@options.allow_update()
def campaign(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a Specification from a yaml file and make a Campaign"""
    result = client.load.campaign_cl(**kwargs)
    output_pydantic_object(result, output, db.Campaign.col_names_for_table)


@load.command()
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
