# pylint: disable=too-many-lines
from typing import TypeVar

import click
import structlog
import uvicorn
from safir.asyncio import run_with_asyncio
from safir.database import create_database_engine, initialize_database

from .. import db
from ..config import config

T = TypeVar("T")


# build the server CLI
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


# Build the client CLI
@click.group(name="client")
@click.version_option(package_name="lsst-cm-service")
def client_top() -> None:
    """Administrative command-line interface client-side commands."""


# Construct client sub-command groups


@client_top.group(name="get")
def get() -> None:
    """Display one or many resources."""


@client_top.group()
def add() -> None:
    """Add a resource"""


@client_top.group()
def load() -> None:
    """Read a yaml file and add stuff to the DB"""


@client_top.group()
def action() -> None:
    """Do something"""


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


@client_top.group(name="script")
def script_group() -> None:
    """Manage Script table"""


@client_top.group(name="queue")
def queue_group() -> None:
    """Manage the processing queue"""


@client_top.group(name="specification")
def specification_group() -> None:
    """Manage Specification table"""


@client_top.group(name="spec_block")
def spec_block_group() -> None:
    """Manage SpecBlock table"""


@client_top.group(name="script_template")
def script_template_group() -> None:
    """Manage ScriptTemplate table"""


@client_top.group(name="pipetask_error_type")
def pipetask_error_type_group() -> None:
    """Manage PipetaskErrorType table"""


@client_top.group(name="pipetask_error")
def pipetask_error_group() -> None:
    """Manage PipetaskError table"""


@client_top.group(name="script_error")
def script_error_group() -> None:
    """Manage ScriptError table"""


@client_top.group(name="product_set")
def product_set_group() -> None:
    """Manage ProductSet table"""


@client_top.group(name="task_set")
def task_set_group() -> None:
    """Manage TaskSet table"""


@client_top.group(name="wms_task_report")
def wms_task_report_group() -> None:
    """Manage WmsTaskReport table"""


@client_top.group(name="script_template_association")
def script_template_association_group() -> None:
    """Manage ScriptTemplateAssociation table"""


@client_top.group(name="spec_block_association")
def spec_block_association_group() -> None:
    """Manage SpecBlockAssociation table"""


@client_top.group(name="script_dependency")
def script_dependency_group() -> None:
    """Manage ScriptDependency table"""


@client_top.group(name="step_dependency")
def step_dependency_group() -> None:
    """Manage StepDependency table"""
