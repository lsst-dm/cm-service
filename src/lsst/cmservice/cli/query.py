from .. import db
from ..client.client import CMClient
from . import options
from .commands import get
from .wrappers import _output_dict, _output_pydantic_list, _output_pydantic_object


@get.command()
@options.cmclient()
@options.output()
def productions(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing productions"""
    result = client.query.get_productions()
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
    result = client.query.get_campaigns(parent_id, parent_name)
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
    result = client.query.get_steps(parent_id, parent_name)
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
    result = client.query.get_groups(parent_id, parent_name)
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
    result = client.query.get_jobs(parent_id, parent_name)
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
    result = client.query.get_scripts(parent_id, parent_name)
    _output_pydantic_list(result, output, db.Script.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def specifications(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing specifications"""
    result = client.query.get_specifications()
    _output_pydantic_list(result, output, db.Specification.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def spec_blocks(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing spec blocks"""
    result = client.query.get_spec_blocks()
    _output_pydantic_list(result, output, db.SpecBlock.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def script_templates(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing script_templates"""
    result = client.query.get_script_templates()
    _output_pydantic_list(result, output, db.ScriptTemplate.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def pipetask_error_types(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing pipetask_error_types"""
    result = client.query.get_pipetask_error_types()
    _output_pydantic_list(result, output, db.PipetaskErrorType.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def pipetask_errors(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing pipetask_errors"""
    result = client.query.get_pipetask_errors()
    _output_pydantic_list(result, output, db.PipetaskError.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def script_errors(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing script_errors"""
    result = client.query.get_script_errors()
    _output_pydantic_list(result, output, db.ScriptError.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def task_sets(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing task_sets"""
    result = client.query.get_task_sets()
    _output_pydantic_list(result, output, db.TaskSet.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def product_sets(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing product_sets"""
    result = client.query.get_product_sets()
    _output_pydantic_list(result, output, db.ProductSet.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def wms_task_reports(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing task_reports"""
    result = client.query.get_wms_task_reports()
    _output_pydantic_list(result, output, db.WmsTaskReport.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def queues(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing queues"""
    result = client.query.get_queues()
    _output_pydantic_list(result, output, db.Queue.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def script_dependencies(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing script_dependencies"""
    result = client.query.get_script_dependencies()
    _output_pydantic_list(result, output, db.ScriptDependency.col_names_for_table)


@get.command()
@options.cmclient()
@options.output()
def step_dependencies(
    client: CMClient,
    output: options.OutputEnum | None,
) -> None:
    """List the existing step_dependencies"""
    result = client.query.get_step_dependencies()
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
    result = client.query.get_element(fullname)
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
    result = client.query.get_script(fullname)
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
    result = client.query.get_job(fullname)
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
    result = client.query.get_spec_block(fullname)
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
    result = client.query.get_specification(fullname)
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
    result = client.query.get_resolved_collections(fullname)
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
    result = client.query.get_collections(fullname)
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
    result = client.query.get_child_config(fullname)
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
    result = client.query.get_data_dict(fullname)
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
    result = client.query.get_spec_aliases(fullname)
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
    value = client.query.get_prerequisites(fullname)
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
    result = client.query.get_element_scripts(fullname, script_name)
    _output_pydantic_list(result, output, db.Script.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def element_all_scripts(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the Scripts used by a partiuclar element"""
    result = client.query.get_element_all_scripts(fullname)
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
    result = client.query.get_element_jobs(fullname)
    _output_pydantic_list(result, output, db.Job.col_names_for_table)


@get.command()
@options.cmclient()
@options.fullname()
@options.output()
def element_sleep(
    client: CMClient,
    fullname: str,
    output: options.OutputEnum | None,
) -> None:
    """Get the Jobs used by a partiuclar element"""
    result = client.query.get_element_sleep(fullname)
    _output_dict({"sleep": result}, output)


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
    result = client.query.get_job_task_sets(fullname)
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
    result = client.query.get_job_wms_reports(fullname)
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
    result = client.query.get_job_product_sets(fullname)
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
    result = client.query.get_job_errors(fullname)
    _output_pydantic_list(result, output, db.PipetaskError.col_names_for_table)
