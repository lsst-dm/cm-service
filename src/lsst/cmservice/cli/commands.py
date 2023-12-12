# pylint: disable=too-many-lines
from typing import Any, TypeVar

import click
import structlog
import uvicorn
from safir.asyncio import run_with_asyncio
from safir.database import create_database_engine, initialize_database

from .. import db
from ..client.client import CMClient
from ..common.enums import StatusEnum
from ..config import config
from . import options
from .wrappers import _output_dict, _output_pydantic_list, _output_pydantic_object

T = TypeVar("T")


@click.group()
@click.version_option(package_name="lsst-cm-service")
def server() -> None:
    """Administrative command-line interface for cm-service."""


@server.command()
@click.option("--reset", is_flag=True, help="Delete all existing database data.")
@run_with_asyncio
async def init(*, reset: bool) -> None:  # pragma: no cover
    """Initialize the service database."""
    logger = structlog.get_logger(config.logger_name)
    engine = create_database_engine(config.database_url, config.database_password)
    await initialize_database(engine, logger, schema=db.Base.metadata, reset=reset)
    await engine.dispose()


@server.command()
@click.option("--port", default=8080, type=int, help="Port to run the application on.")
def run(port: int) -> None:  # pragma: no cover
    """Run the service application (for testing only)."""
    uvicorn.run("lsst.cmservice.main:app", host="0.0.0.0", port=port, reload=True, reload_dirs=["src"])


@click.group(name="client")
@click.version_option(package_name="lsst-cm-service")
def client_top() -> None:
    """Administrative command-line interface client-side commands."""


@client_top.group(name="get")
def get() -> None:
    """Display one or many resources."""


@client_top.group()
def add() -> None:
    """Add a resource"""


@add.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.child_configs()
def groups_(
    client: CMClient,
    fullname: options.PartialOption,
    child_configs: dict,
    output: options.OutputEnum | None,
) -> None:
    """Add Groups to a Step"""
    result = client.add_groups(
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
    result = client.add_steps(
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
    result = client.add_campaign(
        fullname=fullname,
        **child_configs,
    )
    _output_pydantic_object(result, output, db.Campaign.col_names_for_table)


@client_top.group()
def load() -> None:
    """Read a yaml file and add stuff to the DB"""


@load.command()
@options.cmclient()
@options.output()
@options.spec_name()
@options.yaml_file()
def load_specification(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a Specification from a yaml file"""
    result = client.load_specification(**kwargs)
    _output_pydantic_object(result, output, db.Specification.col_names_for_table)


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
def load_campaign(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Load a Specification from a yaml file and make a Campaign"""
    result = client.load_campaign(**kwargs)
    _output_pydantic_object(result, output, db.Campaign.col_names_for_table)


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
    result = client.load_error_types(**kwargs)
    _output_pydantic_list(result, output, db.PipetaskErrorType.col_names_for_table)


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
    result = client.load_manifest_report(**kwargs)
    _output_pydantic_object(result, output, db.Job.col_names_for_table)


@client_top.group()
def action() -> None:
    """Do something"""


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
    changed, status = client.process(
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
    result = client.reset_script(
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
    result = client.retry_script(
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
    result = client.rescue_script(
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
    result = client.mark_script_rescued(
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
    result = client.rematch_errors(**kwargs)
    _output_pydantic_list(result, output, db.PipetaskError.col_names_for_table)


@client_top.group(name="production")
def production() -> None:
    """Manage production table"""


@client_top.group(name="campaign")
def campaign_group() -> None:
    """Manage Campaign table"""


@client_top.group(name="step")
def step_group() -> None:
    """Manage Step table"""


@client_top.group(name="group")
def group_group() -> None:
    """Manage Group table"""


@client_top.group(name="job")
def job_group() -> None:
    """Manage Job table"""


@client_top.group(name="queue")
def queue() -> None:
    """manage the processing queue"""


@queue.command(name="create")
@options.cmclient()
@options.fullname()
@options.interval()
@options.output()
def queue_create(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Create a production"""
    result = client.queue_create(**kwargs)
    _output_pydantic_object(result, output, db.Queue.col_names_for_table)


@queue.command(name="update")
@options.cmclient()
@options.row_id()
@options.fullname()
@options.interval()
@options.output()
def queue_update(
    client: CMClient,
    output: options.OutputEnum | None,
    row_id: int,
    **kwargs: Any,
) -> None:
    """Update a production"""
    result = client.queue_update(row_id, **kwargs)
    _output_pydantic_object(result, output, db.Queue.col_names_for_table)


@queue.command(name="get")
@options.cmclient()
@options.row_id()
@options.output()
def queue_get(
    client: CMClient,
    output: options.OutputEnum | None,
    row_id: int,
) -> None:
    """Update a production"""
    result = client.queue_get(row_id)
    _output_pydantic_object(result, output, db.Queue.col_names_for_table)


@queue.command(name="delete")
@options.cmclient()
@options.row_id()
def queue_delete(
    client: CMClient,
    row_id: int,
) -> None:
    """Update a production"""
    client.queue_delete(row_id)


@queue.command(name="daemon")
@options.cmclient()
@options.row_id()
def queue_dameon(
    client: CMClient,
    row_id: int,
) -> None:
    """Update a production"""
    client.queue_daemon(row_id)
