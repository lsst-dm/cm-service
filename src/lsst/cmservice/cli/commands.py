import json
from collections.abc import Sequence
from typing import Any, TypeVar

import click
import structlog
import uvicorn
import yaml
from pydantic import BaseModel
from safir.asyncio import run_with_asyncio
from safir.database import create_database_engine, initialize_database
from tabulate import tabulate

from .. import db
from ..client import CMClient
from ..common.enums import StatusEnum
from ..config import config
from . import options


def _output_pydantic_object(
    model: BaseModel,
    output: options.OutputEnum | None,
    col_names: list[str] | None = None,
) -> None:
    match output:
        case options.OutputEnum.json:
            click.echo(json.dumps(model.dict(), indent=4))
        case options.OutputEnum.yaml:
            click.echo(yaml.dump(model.dict()))
        case _:
            assert col_names
            the_table = [[getattr(model, col_) for col_ in col_names]]
            click.echo(tabulate(the_table, headers=col_names, tablefmt="plain"))


def _output_pydantic_list(
    models: Sequence[BaseModel],
    output: options.OutputEnum | None,
    col_names: Sequence[str] | None = None,
) -> None:
    the_table = []
    for model_ in models:
        match output:
            case options.OutputEnum.json:
                click.echo(json.dumps(model_.dict(), indent=4))
            case options.OutputEnum.yaml:
                click.echo(yaml.dump(model_.dict()))
            case _:
                assert col_names
                the_table.append([str(getattr(model_, col_)) for col_ in col_names])
    match output:
        case options.OutputEnum.json:
            pass
        case options.OutputEnum.yaml:
            pass
        case _:
            assert col_names
            click.echo(tabulate(the_table, headers=col_names, tablefmt="plain"))


def _output_dict(
    the_dict: dict,
    output: options.OutputEnum | None,
) -> None:
    match output:
        case options.OutputEnum.json:
            click.echo(json.dumps(the_dict, indent=4))
        case options.OutputEnum.yaml:
            click.echo(yaml.dump(the_dict))
        case _:
            for key, val in the_dict.items():
                click.echo(f"{key}: {val}")


T = TypeVar("T")


@click.group()
@click.version_option(package_name="lsst-cm-service")
def main() -> None:
    """Administrative command-line interface for cm-service."""


@main.command()
@click.option("--reset", is_flag=True, help="Delete all existing database data.")
@run_with_asyncio
async def init(*, reset: bool) -> None:  # pragma: no cover
    """Initialize the service database."""
    logger = structlog.get_logger(config.logger_name)
    engine = create_database_engine(config.database_url, config.database_password)
    await initialize_database(engine, logger, schema=db.Base.metadata, reset=reset)
    await engine.dispose()


@main.command()
@click.option("--port", default=8080, type=int, help="Port to run the application on.")
def run(port: int) -> None:  # pragma: no cover
    """Run the service application (for testing only)."""
    uvicorn.run("lsst.cmservice.main:app", host="0.0.0.0", port=port, reload=True, reload_dirs=["src"])


@main.group()
def get() -> None:
    """Display one or many resources."""


@get.command()
@options.cmclient()
@options.output()
def productions(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing productions"""
    result = client.get_productions()
    _output_pydantic_list(result, output, db.Production.col_names_for_table)


@get.command()
@options.cmclient()
@options.parent_name()
@options.parent_id()
@options.output()
def campaigns(
    client: CMClient,
    parent_id: int | None,
    parent_name: str | None,
    output: options.OutputEnum | None,
) -> None:
    """List the existing campaigns

    Specifying either parent-name or parent-id
    will limit the results to only those
    campaigns in the associated production
    """
    result = client.get_campaigns(parent_id, parent_name)
    _output_pydantic_list(result, output, db.Campaign.col_names_for_table)


@get.command()
@options.cmclient()
@options.parent_name()
@options.parent_id()
@options.output()
def steps(
    client: CMClient,
    parent_id: int | None,
    parent_name: str | None,
    output: options.OutputEnum | None,
) -> None:
    """List the existing steps

    Specifying either parent-name or parent-id
    will limit the results to only those
    steps in the associated campaign
    """
    result = client.get_steps(parent_id, parent_name)
    _output_pydantic_list(result, output, db.Step.col_names_for_table)


@get.command()
@options.cmclient()
@options.parent_name()
@options.parent_id()
@options.output()
def groups(
    client: CMClient,
    parent_id: int | None,
    parent_name: str | None,
    output: options.OutputEnum | None,
) -> None:
    """List the existing groups

    Specifying either parent-name or parent-id
    will limit the results to only those
    groups in the associated step
    """
    result = client.get_groups(parent_id, parent_name)
    _output_pydantic_list(result, output, db.Group.col_names_for_table)


@get.command()
@options.cmclient()
@options.parent_name()
@options.parent_id()
@options.output()
def jobs(
    client: CMClient,
    parent_id: int | None,
    parent_name: str | None,
    output: options.OutputEnum | None,
) -> None:
    """List the existing jobs

    Specifying either parent-name or parent-id
    will limit the results to only those
    groups in the associated step
    """
    result = client.get_jobs(parent_id, parent_name)
    _output_pydantic_list(result, output, db.Job.col_names_for_table)


@get.command()
@options.cmclient()
@options.parent_name()
@options.parent_id()
@options.output()
def scripts(
    client: CMClient,
    parent_id: int | None,
    parent_name: str | None,
    output: options.OutputEnum | None,
) -> None:
    """List the existing scripts

    Specifying either parent-name or parent-id
    will limit the results to only those
    groups in the associated element
    """
    result = client.get_scripts(parent_id, parent_name)
    _output_pydantic_list(result, output, db.Script.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def specifications(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing specifications"""
    result = client.get_specifications()
    _output_pydantic_list(result, output, db.Specification.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def spec_blocks(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing spec blocks"""
    result = client.get_spec_blocks()
    _output_pydantic_list(result, output, db.SpecBlock.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def script_templates(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing script_templates"""
    result = client.get_script_templates()
    _output_pydantic_list(result, output, db.ScriptTemplate.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def pipetask_error_types(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing pipetask_error_types"""
    result = client.get_pipetask_error_types()
    _output_pydantic_list(result, output, db.PipetaskErrorType.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def pipetask_errors(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing pipetask_errors"""
    result = client.get_pipetask_errors()
    _output_pydantic_list(result, output, db.PipetaskError.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def script_errors(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing script_errors"""
    result = client.get_script_errors()
    _output_pydantic_list(result, output, db.ScriptError.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def task_sets(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing task_sets"""
    result = client.get_task_sets()
    _output_pydantic_list(result, output, db.TaskSet.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def product_sets(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing product_sets"""
    result = client.get_product_sets()
    _output_pydantic_list(result, output, db.ProductSet.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def wms_task_reports(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing task_reports"""
    result = client.get_wms_task_reports()
    _output_pydantic_list(result, output, db.WmsTaskReport.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def script_dependencies(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing script_dependencies"""
    result = client.get_script_dependencies()
    _output_pydantic_list(result, output, db.ScriptDependency.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def step_dependencies(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing step_dependencies"""
    result = client.get_step_dependencies()
    _output_pydantic_list(result, output, db.StepDependency.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def element(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get a particular element"""
    result = client.get_element(fullname)
    _output_pydantic_object(result, output, db.ElementMixin.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def script(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get a particular script"""
    result = client.get_script(fullname)
    _output_pydantic_object(result, output, db.Script.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def job(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get a particular job"""
    result = client.get_job(fullname)
    _output_pydantic_object(result, output, db.Job.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def obj_spec_block(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the SpecBlock corresponding to a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.get_spec_block(fullname)
    _output_pydantic_object(result, output, db.SpecBlock.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def obj_specification(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the Specification corresponding to a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.get_specification(fullname)
    _output_pydantic_object(result, output, db.Specification.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def obj_resolved_collections(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the resovled collection for a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.get_resolved_collections(fullname)
    _output_dict(result, output)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def obj_collections(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the collection parameters for a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.get_collections(fullname)
    _output_dict(result, output)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def obj_child_config(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the child_config parameters for a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.get_child_config(fullname)
    _output_dict(result, output)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def obj_data_dict(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the data_dict parameters for a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.get_data_dict(fullname)
    _output_dict(result, output)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def obj_spec_aliases(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the spec_aliases parameters for a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.get_spec_aliases(fullname)
    _output_dict(result, output)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def check_prerequisites(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Check if prerequisites are done for a partiuclar node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    value = client.get_prerequisites(fullname)
    _output_dict({"value": value}, output)


@get.command()
@options.cmclient()
@options.fullname()
@options.script_name()
@options.output()
def element_scripts(
    client: CMClient,
    fullname: str,
    script_name: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the Scripts used by a partiuclar element"""
    result = client.get_element_scripts(fullname, script_name)
    _output_pydantic_list(result, output, db.Script.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def element_jobs(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the Jobs used by a partiuclar element"""
    result = client.get_element_jobs(fullname)
    _output_pydantic_list(result, output, db.Job.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def job_task_sets(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the TaskSets for a particular Job"""
    result = client.get_job_task_sets(fullname)
    _output_pydantic_list(result, output, db.TaskSet.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def job_wms_reports(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the WmsReports for a particular Job"""
    result = client.get_job_wms_reports(fullname)
    _output_pydantic_list(result, output, db.WmsTaskReport.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def job_product_sets(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the ProductSets for a particular Job"""
    result = client.get_job_product_sets(fullname)
    _output_pydantic_list(result, output, db.ProductSet.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def job_errors(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the PipetaskErrors for a particular Job"""
    result = client.get_job_errors(fullname)
    _output_pydantic_list(result, output, db.PipetaskError.col_names_for_table)


@main.group()
def update() -> None:
    """Update a resource."""


@update.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.status()
def status_(
    client: CMClient,
    fullname: options.PartialOption,
    output: options.OutputEnum | None,
    status: StatusEnum,
) -> None:
    """Update the status of a particular Node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    status = client.update_status(
        fullname=fullname,
        status=status,
    )
    _output_dict({"status": status}, output)


@update.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.update_dict()
def collections(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Update collections configuration of particular Node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.update_collections(**kwargs)
    _output_dict(result, output)


@update.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.update_dict()
def child_config(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Update child_config configuration of particular Node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.update_child_config(**kwargs)
    _output_dict(result, output)


@update.command()
@options.cmclient()
@options.fullname()
@options.output()
@options.update_dict()
def data_dict(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Update data_dict configuration of particular Node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    result = client.update_data_dict(**kwargs)
    _output_dict(result, output)


@main.group()
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


@main.group()
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


@main.group()
def action() -> None:
    """Do something"""


@action.command()
@options.cmclient()
@options.fullname()
@options.output()
def process(
    client: CMClient,
    fullname: options.PartialOption,
    output: options.OutputEnum | None,
) -> None:
    """Process an node

    By default this selects elements, but
    table-type can be set to 'script'
    """
    status = client.process(
        fullname=fullname,
    )
    _output_dict({"status": status}, output)


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


@main.group()
def manage() -> None:
    """manage the DB directly"""


@manage.group()
def production() -> None:
    """Manage production table"""


@production.command(name="create")
@options.cmclient()
@options.name()
@options.output()
def production_create(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Create a production"""
    result = client.production_create(**kwargs)
    _output_pydantic_object(result, output, db.Production.col_names_for_table)


@production.command(name="update")
@options.cmclient()
@options.id()
@options.name()
@options.output()
def prodcution_update(
    client: CMClient,
    output: options.OutputEnum | None,
    id: int,
    **kwargs: Any,
) -> None:
    """Update a production"""
    result = client.production_update(id, **kwargs)
    _output_pydantic_object(result, output, db.Production.col_names_for_table)


@production.command(name="delete")
@options.cmclient()
@options.id()
def prodcution_delete(
    client: CMClient,
    id: int,
) -> None:
    """Update a production"""
    client.production_delete(id)


@manage.group(name="campaign")
def campaign_command() -> None:
    """Manage production table"""


@campaign_command.command(name="create")
@options.cmclient()
@options.name()
@options.parent_name()
@options.spec_block_name()
@options.data()
@options.child_config()
@options.collections()
@options.spec_aliases()
@options.handler()
@options.output()
def campagin_create(
    client: CMClient,
    output: options.OutputEnum | None,
    **kwargs: Any,
) -> None:
    """Create a campaign"""
    result = client.campaign_create(**kwargs)
    _output_pydantic_object(result, output, db.Campaign.col_names_for_table)


@campaign_command.command(name="update")
@options.cmclient()
@options.name()
@options.parent_name()
@options.spec_block_name()
@options.data()
@options.child_config()
@options.collections()
@options.spec_aliases()
@options.handler()
@options.output()
@options.id()
def campaign_update(
    client: CMClient,
    output: options.OutputEnum | None,
    id: int,
    **kwargs: Any,
) -> None:
    """Update a campaign"""
    result = client.campaign_update(id, **kwargs)
    _output_pydantic_object(result, output, db.Campaign.col_names_for_table)


@campaign_command.command(name="delete")
@options.cmclient()
@options.id()
def campaign_delete(
    client: CMClient,
    id: int,
) -> None:
    """Delete a campaign"""
    client.campaign_delete(id)
