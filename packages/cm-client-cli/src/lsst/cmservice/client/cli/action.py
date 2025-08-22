from typing import Any

import click

from .. import StatusEnum, db
from ..client.client import CMClient
from . import options
from .wrappers import output_dict, output_pydantic_list, output_pydantic_object


@click.group(name="action")
def action_group() -> None:
    """Do something"""


@action_group.command()
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
    output_dict({"changed": changed, "status": status}, output)


@action_group.command()
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
    output_pydantic_object(result, output, db.Script.col_names_for_table)


@action_group.command()
@options.cmclient()
@options.fullname()
@options.output()
def rescue_job(
    client: CMClient,
    fullname: options.PartialOption,
    output: options.OutputEnum | None,
) -> None:
    """Create a new version of a job to rescue it

    This can only be run on rescuable jobs.
    """
    result = client.action.rescue_job(
        fullname=fullname,
    )
    output_pydantic_object(result, output, db.Job.col_names_for_table)


@action_group.command()
@options.cmclient()
@options.fullname()
@options.output()
def mark_job_rescued(
    client: CMClient,
    fullname: options.PartialOption,
    output: options.OutputEnum | None,
) -> None:
    """Mark a job as rescued

    This is usually done automatically when
    the job is accepted
    """
    result = client.action.mark_job_rescued(
        fullname=fullname,
    )
    output_pydantic_list(result, output, db.Job.col_names_for_table)


@action_group.command()
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
    output_pydantic_list(result, output, db.PipetaskError.col_names_for_table)
