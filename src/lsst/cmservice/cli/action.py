from typing import Any

from .. import db
from ..client.client import CMClient
from ..common.enums import StatusEnum
from . import options
from .commands import action
from .wrappers import _output_dict, _output_pydantic_list, _output_pydantic_object


@action.command()
@options.cmclient()
@options.fullname()
@options.fake_status()
@options.output()
def process(
    client: CMClient,
    fullname: options.PartialOption,
    fake_status: StatusEnum | None,
    output: options.OutputEnum | None,
) -> None:
    """Process an node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    changed, status = client.action.process(
        fullname=fullname,
        fake_status=fake_status,
    )
    _output_dict({"changed": changed, "status": status}, output)


@action.command()
@options.cmclient()
@options.fullname()
@options.status()
@options.output()
def reset_script(
    client: CMClient,
    fullname: options.PartialOption,
    status: StatusEnum,
    output: options.OutputEnum | None,
) -> None:
    """Reset as script to an earlier status

    This will removed log files and
    the script file, as needed.
    """
    result = client.action.reset_script(
        fullname=fullname,
        status=status,
    )
    _output_pydantic_object(result, output, db.Script.col_names_for_table)


@action.command()
@options.cmclient()
@options.fullname()
@options.script_name()
@options.output()
def retry_script(
    client: CMClient,
    fullname: options.PartialOption,
    script_name: options.PartialOption,
    output: options.OutputEnum | None,
) -> None:
    """Create a new version of a script to retry it

    This will mark the current version as superseded.
    This can only be run on failed/rejected scripts.
    """
    result = client.action.retry_script(
        fullname=fullname,
        script_name=script_name,
    )
    _output_pydantic_object(result, output, db.Script.col_names_for_table)


@action.command()
@options.cmclient()
@options.fullname()
@options.script_name()
@options.output()
def rescue_script(
    client: CMClient,
    fullname: options.PartialOption,
    script_name: options.PartialOption,
    output: options.OutputEnum | None,
) -> None:
    """Create a new version of a script to rescue it

    This can only be run on rescuable scripts.
    """
    result = client.action.rescue_script(
        fullname=fullname,
        script_name=script_name,
    )
    _output_pydantic_object(result, output, db.Script.col_names_for_table)


@action.command()
@options.cmclient()
@options.fullname()
@options.script_name()
@options.output()
def mark_script_rescued(
    client: CMClient,
    fullname: options.PartialOption,
    script_name: options.PartialOption,
    output: options.OutputEnum | None,
) -> None:
    """Mark a script as rescued

    This is usually done automatically when
    the script is accepted
    """
    result = client.action.mark_script_rescued(
        fullname=fullname,
        script_name=script_name,
    )
    _output_pydantic_list(result, output, db.Script.col_names_for_table)


@action.command()
@options.cmclient()
@options.rematch()
@options.output()
def rematch(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Rematch the errors"""
    result = client.action.rematch_errors(**kwargs)
    _output_pydantic_list(result, output, db.PipetaskError.col_names_for_table)
