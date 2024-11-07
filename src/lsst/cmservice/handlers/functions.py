import os
from collections.abc import Mapping
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.ctrl.bps.bps_reports import compile_job_summary
from lsst.ctrl.bps.wms_service import WmsJobReport, WmsRunReport, WmsStates

from ..common.enums import StatusEnum
from ..common.errors import CMYamlParseError
from ..db.campaign import Campaign
from ..db.job import Job
from ..db.pipetask_error import PipetaskError
from ..db.pipetask_error_type import PipetaskErrorType
from ..db.product_set import ProductSet
from ..db.script_template import ScriptTemplate
from ..db.spec_block import SpecBlock
from ..db.specification import Specification
from ..db.step import Step
from ..db.step_dependency import StepDependency
from ..db.task_set import TaskSet
from ..db.wms_task_report import WmsTaskReport


def update_include_dict(
    orig_dict: dict[str, Any],
    include_dict: dict[str, Any],
) -> None:
    """Update a dict by updating (instead of replacing) sub-dicts

    Parameters
    ----------
    orig_dict: dict[str, Any]
        Original dict
    include_dict: dict[str, Any],
        Dict used to update the original
    """
    for key, val in include_dict.items():
        if isinstance(val, Mapping) and key in orig_dict:
            orig_dict[key].update(val)
        else:
            orig_dict[key] = val


async def upsert_spec_block(
    session: async_scoped_session,
    config_values: dict,
    loaded_specs: dict,
    *,
    allow_update: bool = False,
) -> SpecBlock | None:
    """Upsert and return a SpecBlock

    This will create a new SpecBlock, or update an existing one

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    config_values: dict
        Values for the SpecBlock

    loaded_specs: dict
        Already loaded SpecBlocks, used for include statments

    allow_update: bool
        Allow updating existing blocks

    Returns
    -------
    spec_block: SpecBlock
        Newly created or updated SpecBlock
    """
    key = config_values.pop("name")
    loaded_specs[key] = config_values
    spec_block_q = select(SpecBlock).where(SpecBlock.fullname == key)
    spec_block_result = await session.scalars(spec_block_q)
    spec_block = spec_block_result.first()
    if spec_block and not allow_update:
        print(f"SpecBlock {key} already defined, leaving it unchanged")
        return spec_block
    includes = config_values.pop("includes", [])
    block_data = config_values.copy()
    include_data: dict[str, Any] = {}
    for include_ in includes:
        if include_ in loaded_specs:
            update_include_dict(include_data, loaded_specs[include_])
        else:
            spec_block_ = await SpecBlock.get_row_by_fullname(session, include_)
            update_include_dict(
                include_data,
                {
                    "handler": spec_block_.handler,
                    "data": spec_block_.data,
                    "collections": spec_block_.collections,
                    "child_config": spec_block_.child_config,
                    "spec_aliases": spec_block_.spec_aliases,
                    "scripts": spec_block_.scripts,
                    "steps": spec_block_.steps,
                },
            )

    for include_key, include_val in include_data.items():
        if include_key in block_data and isinstance(include_val, Mapping):
            block_data[include_key].update(include_val)
        else:
            block_data[include_key] = include_val

    handler = block_data.pop("handler", None)
    if spec_block is None:
        return await SpecBlock.create_row(
            session,
            name=key,
            handler=handler,
            data=block_data.get("data"),
            collections=block_data.get("collections"),
            child_config=block_data.get("child_config"),
            scripts=block_data.get("scripts"),
            steps=block_data.get("steps"),
        )
    return await spec_block.update_values(
        session,
        name=key,
        handler=handler,
        data=block_data.get("data"),
        collections=block_data.get("collections"),
        child_config=block_data.get("child_config"),
        scripts=block_data.get("scripts"),
        steps=block_data.get("steps"),
    )


async def upsert_script_template(
    session: async_scoped_session,
    config_values: dict,
    *,
    allow_update: bool = False,
) -> ScriptTemplate | None:
    """Upsert and return a ScriptTemplate

    This will create a new ScriptTemplate, or update an existing one

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    config_values: dict
        Values for the ScriptTemplate

    allow_update: bool
        Allow updating existing templates

    Returns
    -------
    script_template: ScriptTemplate
        Newly created or updated ScriptTemplate
    """
    key = config_values.pop("name")
    script_template_q = select(ScriptTemplate).where(ScriptTemplate.fullname == key)
    script_template_result = await session.scalars(script_template_q)
    script_template = script_template_result.first()
    if script_template and not allow_update:
        print(f"ScriptTemplate {key} already defined, leaving it unchanged")
        return script_template
    if script_template is None:
        return await ScriptTemplate.load(
            session,
            name=key,
            file_path=config_values["file_path"],
        )

    return await script_template.update_from_file(
        session,
        name=key,
        file_path=config_values["file_path"],
    )


async def upsert_specification(
    session: async_scoped_session,
    config_values: dict,
    *,
    allow_update: bool = False,
) -> Specification | None:
    """Upsert and return a Specification

    This will create a new Specification, or update an existing one

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    config_values: dict
        Values for the ScriptTemplate

    allow_update: bool
        Allow updating existing templates

    Returns
    -------
    specification: Specification
        Newly created or updated Specification
    """
    spec_name = config_values["name"]

    spec_q = select(Specification).where(Specification.name == spec_name)
    spec_result = await session.scalars(spec_q)
    specification = spec_result.first()
    if specification and not allow_update:
        print(f"Specification {spec_name} already defined, leaving it unchanged")
        return specification
    if specification is None:
        return await Specification.create_row(session, **config_values)
    return await specification.update_values(session, **config_values)


async def load_specification(
    session: async_scoped_session,
    yaml_file: str,
    loaded_specs: dict | None = None,
    *,
    allow_update: bool = False,
) -> Specification | None:
    """Load Specification, SpecBlock, and ScriptTemplate objects from a yaml
    file, including from files referenced by Include blocks. Return the last
    Specification object in the file.

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    yaml_file: str
        File in question

    loaded_specs: dict
        Already loaded SpecBlocks, used for include statments

    allow_update: bool
        Allow updating existing items

    Returns
    -------
    specification: Specification
        Newly created Specification
    """
    if loaded_specs is None:
        loaded_specs = {}

    specification = None
    with open(yaml_file, encoding="utf-8") as fin:
        spec_data = yaml.safe_load(fin)

    for config_item in spec_data:
        if "Imports" in config_item:
            imports = config_item["Imports"]
            for import_ in imports:
                await load_specification(
                    session,
                    os.path.abspath(os.path.expandvars(import_)),
                    loaded_specs,
                    allow_update=allow_update,
                )
        elif "SpecBlock" in config_item:
            await upsert_spec_block(
                session,
                config_item["SpecBlock"],
                loaded_specs,
                allow_update=allow_update,
            )
        elif "ScriptTemplate" in config_item:
            await upsert_script_template(
                session,
                config_item["ScriptTemplate"],
                allow_update=allow_update,
            )
        elif "Specification" in config_item:
            specification = await upsert_specification(
                session,
                config_item["Specification"],
                allow_update=allow_update,
            )
        else:  # pragma: no cover
            good_keys = "ScriptTemplate | SpecBlock | Specification | Imports"
            raise CMYamlParseError(f"Expecting one of {good_keys} not: {spec_data.keys()})")

    return specification


async def add_step_prerequisite(
    session: async_scoped_session,
    depend_id: int,
    prereq_id: int,
) -> StepDependency:
    """Create and return a StepDependency

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    depend_id: int
        Id of dependency Step

    prereq_id: int
        Id of prerequisite Step

    Returns
    -------
    step_dependency: StepDependency
        Newly created StepDependency
    """
    return await StepDependency.create_row(
        session,
        prereq_id=prereq_id,
        depend_id=depend_id,
    )


async def add_steps(
    session: async_scoped_session,
    campaign: Campaign,
    step_config_list: list[dict[str, dict]],
) -> Campaign:
    """Add steps to a Campaign

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    campaign: Campaign
        Campaign in question

    step_config_list: list[dict[str, dict]]
        Configuration for the steps

    Returns
    -------
    campaign : Campaign
        Campaign in question
    """
    spec_aliases = await campaign.get_spec_aliases(session)

    current_steps = await campaign.children(session)
    child_config = await campaign.get_child_config(session)

    step_ids_dict = {step_.name: step_.id for step_ in current_steps}

    prereq_pairs = []
    for step_ in step_config_list:
        try:
            step_config_ = step_["Step"]
        except KeyError as msg:  # pragma: no cover
            raise CMYamlParseError(f"Expecting Step not: {step_.keys()}") from msg
        child_name_ = step_config_.pop("name")
        spec_block_name = step_config_.pop("spec_block")
        if spec_block_name is None:  # pragma: no cover
            raise CMYamlParseError(
                f"Step {child_name_} of {campaign.fullname} does contain 'spec_block'",
            )
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        update_include_dict(step_config_, child_config.get(child_name_, {}))

        new_step = await Step.create_row(
            session,
            name=child_name_,
            spec_block_name=spec_block_name,
            parent_name=campaign.fullname,
            **step_config_,
        )
        await session.refresh(new_step)
        step_ids_dict[child_name_] = new_step.id
        prereqs_names = step_config_.pop("prerequisites", [])
        prereq_pairs += [(child_name_, prereq_) for prereq_ in prereqs_names]

    for depend_name, prereq_name in prereq_pairs:
        prereq_id = step_ids_dict[prereq_name]
        depend_id = step_ids_dict[depend_name]
        new_depend = await add_step_prerequisite(session, depend_id, prereq_id)
        await session.refresh(new_depend)

    await session.refresh(campaign)
    return campaign


async def match_pipetask_error(
    session: async_scoped_session,
    task_name: str,
    diagnostic_message: str,
) -> PipetaskErrorType | None:
    """Match task_name and diagnostic_message to PipetaskErrorType

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    task_name: str
        Name of associated Pipetask

    diagnostic_message: str
        Diagnostic message of error

    Returns
    -------
    error_type : PipetaskErrorType | None
        Matched error type, or None for no match
    """
    for pipetask_error_type_ in await PipetaskErrorType.get_rows(session):
        if pipetask_error_type_.match(task_name, diagnostic_message):
            return pipetask_error_type_
    return None


async def load_manifest_report(
    session: async_scoped_session,
    job_name: str,
    yaml_file: str,
    fake_status: StatusEnum | None = None,
) -> Job:
    """Parse and load output of pipetask report

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    job_name: str
        Name of associated Job

    yaml_file: str
        Pipetask report yaml file

    fake_status: StatusEnum | None
        If set, return this status

    Returns
    -------
    job : Job
        Associated Job
    """
    job = await Job.get_row_by_fullname(session, job_name)
    if fake_status is not None:
        return job

    with open(yaml_file, encoding="utf-8") as fin:
        manifest_data = yaml.safe_load(fin)

    for task_name_, task_data_ in manifest_data.items():
        failed_quanta = task_data_.get("failed_quanta", {})
        outputs = task_data_.get("outputs", {})
        n_expected = task_data_.get("n_expected", 0)
        n_failed = len(failed_quanta)
        n_failed_upstream = task_data_.get("n_quanta_blocked", 0)
        n_done = task_data_.get("n_succeeded", 0)

        try:
            task_set = await TaskSet.create_row(
                session,
                job_id=job.id,
                name=task_name_,
                fullname=f"{job_name}/{task_name_}",
                n_expected=n_expected,
                n_done=n_done,
                n_failed=n_failed,
                n_failed_upstream=n_failed_upstream,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            task_set = await TaskSet.get_row_by_fullname(session, f"{job_name}/{task_name_}")
            task_set = await TaskSet.update_row(
                session,
                row_id=task_set.id,
                job_id=job.id,
                name=task_name_,
                fullname=f"{job_name}/{task_name_}",
                n_expected=n_expected,
                n_done=n_done,
                n_failed=n_failed,
                n_failed_upstream=n_failed_upstream,
            )

        for data_type_, counts_ in outputs.items():
            try:
                product_set = await ProductSet.create_row(
                    session,
                    job_id=job.id,
                    task_id=task_set.id,
                    name=data_type_,
                    fullname=f"{task_set.fullname}/{data_type_}",
                    n_expected=counts_.get("expected", 0),
                    n_done=counts_.get("produced", 0),
                    n_failed=counts_.get("failed", 0),
                    n_failed_upstream=counts_.get("blocked", 0),
                    n_missing=counts_.get("not_produced", 0),
                )
            except Exception:  # pylint: disable=broad-exception-caught
                product_set = await ProductSet.get_row_by_fullname(
                    session,
                    f"{task_set.fullname}/{data_type_}",
                )
                product_set = await ProductSet.update_row(
                    session,
                    row_id=product_set.id,
                    job_id=job.id,
                    task_id=task_set.id,
                    name=data_type_,
                    fullname=f"{task_set.fullname}/{data_type_}",
                    n_expected=counts_.get("expected", 0),
                    n_done=counts_.get("produced", 0),
                    n_failed=counts_.get("failed", 0),
                    n_failed_upstream=counts_.get("blocked", 0),
                    n_missing=counts_.get("not_produced", 0),
                )

        for failed_quanta_uuid_, failed_quanta_data_ in failed_quanta.items():
            diagnostic_message_list = failed_quanta_data_["error"]
            if diagnostic_message_list:
                diagnostic_message = diagnostic_message_list[-1]
            else:
                diagnostic_message = "Super-unhelpful empty message"

            error_type_id = await match_pipetask_error(
                session,
                task_name_,
                diagnostic_message,
            )
            _new_pipetask_error = await PipetaskError.create_row(
                session,
                error_type_id=error_type_id,
                task_id=task_set.id,
                quanta=failed_quanta_uuid_,
                data_id=failed_quanta_data_["data_id"],
                diagnostic_message=diagnostic_message,
            )

    return job


def status_from_bps_report(
    wms_run_report: WmsRunReport | None,
    fake_status: StatusEnum | None,
) -> StatusEnum:  # pragma: no cover
    """Decide the status for a workflow for a bps report

    Parameters
    ----------
    wms_run_report: WmsRunReport,
        bps report return object

    Returns
    -------
    status: StatusEnum
        The status to set for the bps_report script
    """
    if wms_run_report is None:
        return fake_status

    the_state = wms_run_report.state
    # We treat RUNNING as running from the CM point of view,
    if the_state == WmsStates.RUNNING:
        return StatusEnum.running
    # If the workflow is succeeded we can mark the script as accepted
    if the_state == WmsStates.SUCCEEDED:
        return StatusEnum.accepted
    # These status either should not happen.  We will mark the script as failed
    if the_state in [
        WmsStates.UNKNOWN,
        WmsStates.MISFIT,
        WmsStates.PRUNED,
        WmsStates.UNREADY,
        WmsStates.READY,
        WmsStates.HELD,
        WmsStates.PENDING,
    ]:
        return StatusEnum.failed
    # If we get here, the job should be in WmsStates.FAILED or
    # WmsStates.DELETED
    assert the_state in [WmsStates.FAILED, WmsStates.DELETED]
    # Ok, now we should investigate what happened.

    # First, did final job run successfully.
    final_job: WmsJobReport | None = None
    for job_ in wms_run_report.jobs:
        if job_.name == "finalJob":
            final_job = job_

    # No final job, we bail and ask for help
    if final_job is None:
        return StatusEnum.reviewable

    # If the final job did succeed, we want to accept this script
    # b/c we want pipetask report to run
    if final_job.state == WmsStates.SUCCEEDED:
        return StatusEnum.accepted

    # If the final job did not succeed, we bail and ask for help
    return StatusEnum.reviewable


async def load_wms_reports(
    session: async_scoped_session,
    job: Job,
    wms_run_report: WmsRunReport | None,
) -> Job:  # pragma: no cover
    """Parse and load output of bps report

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    job_name: str
        Name of associated Job

    wms_run_report: WmsRunReport | None
        bps report return object

    Returns
    -------
    job : Job
        Associated Job
    """
    if wms_run_report is None:
        return job
    if wms_run_report.job_summary is None:
        wms_run_report.job_summary = compile_job_summary(wms_run_report.jobs)
    for task_name, job_summary in wms_run_report.job_summary.items():
        fullname = f"{job.fullname}/{task_name}"
        wms_dict = {f"n_{wms_state_.name.lower()}": count_ for wms_state_, count_ in job_summary.items()}
        report: WmsTaskReport | None = None
        try:
            report = await WmsTaskReport.get_row_by_fullname(session, fullname)
            await report.update_values(session, **wms_dict)
        except Exception:  # pylint: disable=broad-exception-caught
            _report = await WmsTaskReport.create_row(
                session,
                job_id=job.id,
                name=task_name,
                fullname=fullname,
                **wms_dict,
            )
    return job


async def load_error_types(
    session: async_scoped_session,
    yaml_file: str,
) -> list[PipetaskErrorType]:
    """Parse and load error types

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    yaml_file: str
        Error type definition yaml file

    Returns
    -------
    error_types : list[PipetaskErrorType]
        Newly loaded error types
    """
    with open(yaml_file, encoding="utf-8") as fin:
        error_types = yaml.safe_load(fin)

    ret_list: list[PipetaskErrorType] = []
    for error_type_ in error_types:
        try:
            val = error_type_["PipetaskErrorType"]
        except KeyError as msg:  # pragma: no cover
            raise CMYamlParseError(f"Expecting PipetaskErrorType items not: {error_type_.keys()})") from msg

        new_error_type = await PipetaskErrorType.create_row(session, **val)
        ret_list.append(new_error_type)

    return ret_list


async def compute_job_status(
    session: async_scoped_session,
    job: Job,
) -> StatusEnum:
    await session.refresh(
        job,
        attribute_names=["wms_reports_", "errors_", "tasks_", "products_"],
    )

    if job.errors_:
        return StatusEnum.reviewable

    return StatusEnum.accepted
