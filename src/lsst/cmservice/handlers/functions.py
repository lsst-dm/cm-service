import os
from collections.abc import Mapping
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.ctrl.bps.wms_service import WmsRunReport

from ..common.errors import CMYamlParseError
from ..db.campaign import Campaign
from ..db.group import Group
from ..db.job import Job
from ..db.pipetask_error import PipetaskError
from ..db.pipetask_error_type import PipetaskErrorType
from ..db.product_set import ProductSet
from ..db.script_template import ScriptTemplate
from ..db.script_template_association import ScriptTemplateAssociation
from ..db.spec_block import SpecBlock
from ..db.spec_block_association import SpecBlockAssociation
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


async def create_spec_block(
    session: async_scoped_session,
    config_values: dict,
    loaded_specs: dict,
) -> SpecBlock | None:
    """Create and return a SpecBlock

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    config_values: dict
        Values for the SpecBlock

    loaded_specs: dict
        Already loaded SpecBlocks, used for include statments

    Returns
    -------
    spec_block: SpecBlock
        Newly created SpecBlock
    """
    key = config_values.pop("name")
    loaded_specs[key] = config_values
    spec_block_q = select(SpecBlock).where(SpecBlock.fullname == key)
    spec_block_result = await session.scalars(spec_block_q)
    spec_block = spec_block_result.first()
    if spec_block:
        print(f"SpecBlock {key} already defined, skipping it")
        return None
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


async def create_script_template(
    session: async_scoped_session,
    config_values: dict,
) -> ScriptTemplate | None:
    """Create and return a ScriptTemplate

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    config_values: dict
        Values for the ScriptTemplate

    Returns
    -------
    script_template: ScriptTemplate
        Newly created ScriptTemplate
    """
    key = config_values.pop("name")
    script_template_q = select(ScriptTemplate).where(ScriptTemplate.fullname == key)
    script_template_result = await session.scalars(script_template_q)
    script_template = script_template_result.first()
    if script_template:
        print(f"ScriptTemplate {key} already defined, skipping it")
        return None
    return await ScriptTemplate.load(
        session,
        name=key,
        file_path=config_values["file_path"],
    )


async def create_specification(
    session: async_scoped_session,
    config_values: dict,
) -> Specification | None:
    """Create and return a Specification

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    config_values: dict
        Values for the ScriptTemplate

    Returns
    -------
    specification: Specification
        Newly created Specification
    """
    spec_name = config_values["name"]
    script_templates = config_values.get("script_templates", [])
    spec_blocks = config_values.get("spec_blocks", [])

    async with session.begin_nested():
        spec_q = select(Specification).where(Specification.name == spec_name)
        spec_result = await session.scalars(spec_q)
        specification = spec_result.first()
        if specification is None:
            specification = Specification(name=spec_name)
            session.add(specification)

        for script_list_item_ in script_templates:
            try:
                script_template_config_ = script_list_item_["ScriptTemplateAssociation"]
            except KeyError as msg:
                raise CMYamlParseError(
                    f"Expected ScriptTemplateAssociation not {list(script_list_item_.keys())}",
                ) from msg
            try:
                _new_script_template_assoc = await ScriptTemplateAssociation.create_row(
                    session,
                    spec_name=spec_name,
                    **script_template_config_,
                )
            except IntegrityError:
                print("ScriptTemplateAssociation already defined, skipping it")
        for spec_block_list_item_ in spec_blocks:
            try:
                spec_block_config_ = spec_block_list_item_["SpecBlockAssociation"]
            except KeyError as msg:
                raise CMYamlParseError(
                    f"Expected SpecBlockAssociation not {list(spec_block_list_item_.keys())}",
                ) from msg
            try:
                _new_spec_block_assoc = await SpecBlockAssociation.create_row(
                    session,
                    spec_name=spec_name,
                    **spec_block_config_,
                )
            except IntegrityError:
                print("SpecBlockAssociation already defined, skipping it")
        await session.commit()
        return specification


async def load_specification(
    session: async_scoped_session,
    yaml_file: str,
    loaded_specs: dict | None = None,
) -> Specification | None:
    """Read a yaml file and create Specification objects

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    yaml_file: str
        File in question

    loaded_specs: dict
        Already loaded SpecBlocks, used for include statments

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
                )
        elif "SpecBlock" in config_item:
            async with session.begin_nested():
                await create_spec_block(
                    session,
                    config_item["SpecBlock"],
                    loaded_specs,
                )
        elif "ScriptTemplate" in config_item:
            async with session.begin_nested():
                await create_script_template(
                    session,
                    config_item["ScriptTemplate"],
                )
        elif "Specification" in config_item:
            async with session.begin_nested():
                specification = await create_specification(
                    session,
                    config_item["Specification"],
                )
        else:
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
    step_ids_dict = {step_.name: step_.id for step_ in current_steps}

    prereq_pairs = []
    for step_ in step_config_list:
        try:
            step_config_ = step_["Step"]
        except KeyError as msg:
            raise CMYamlParseError(f"Expecting Step not: {step_.keys()}") from msg
        child_name_ = step_config_.pop("name")
        spec_block_name = step_config_.pop("spec_block")
        if spec_block_name is None:
            raise CMYamlParseError(
                f"Step {child_name_} of {campaign.fullname} does contain 'spec_block'",
            )
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
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

    async with session.begin_nested():
        await session.refresh(campaign)
    return campaign


async def add_groups(
    session: async_scoped_session,
    step: Step,
    child_configs: dict,
) -> Step:
    """Add Groups to a Step

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    step: Step
        Step in question

    child_configs: dict
        Configuration for the Groups

    Returns
    -------
    step: Step
        Step in question
    """
    spec_aliases = await step.get_spec_aliases(session)

    current_groups = await step.children(session)
    n_groups = len(list(current_groups))
    i = n_groups
    for child_name_, child_config_ in child_configs.items():
        spec_block_name = child_config_.pop("spec_block", None)
        if spec_block_name is None:
            raise CMYamlParseError(
                f"child_config_ {child_name_} of {step.fullname} does contain 'spec_block'",
            )
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        await Group.create_row(
            session,
            name=f"group{i}",
            spec_block_name=spec_block_name,
            parent_name=step.fullname,
            **child_config_,
        )
        i += 1

    async with session.begin_nested():
        await session.refresh(step)
    return step


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

    Returns
    -------
    job : Job
        Associated Job
    """
    with open(yaml_file, encoding="utf-8") as fin:
        manifest_data = yaml.safe_load(fin)

    job = await Job.get_row_by_fullname(session, job_name)

    for task_name_, task_data_ in manifest_data.items():
        failed_quanta = task_data_.get("failed_quanta", {})
        outputs = task_data_.get("outputs", {})
        n_expected = task_data_.get("n_expected", 0)
        n_failed = len(failed_quanta)
        n_failed_upstream = task_data_.get("n_quanta_blocked", 0)
        n_done = n_expected - n_failed - n_failed_upstream

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
        except Exception:
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
                    n_failed=counts_.get("missing_failed", 0),
                    n_failed_upstream=counts_.get("missing_upsteam_failed", 0),
                    n_missing=counts_.get("missing_not_produced", 0),
                )
            except Exception:
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
                    n_failed=counts_.get("missing_failed", 0),
                    n_failed_upstream=counts_.get("missing_upsteam_failed", 0),
                    n_missing=counts_.get("missing_not_produced", 0),
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


async def load_wms_reports(
    session: async_scoped_session,
    job: Job,
    wms_run_report: WmsRunReport,
) -> Job:
    """Parse and load output of bps report

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    job_name: str
        Name of associated Job

    wms_run_report: WmsRunReport
        bps report return object

    Returns
    -------
    job : Job
        Associated Job
    """
    for task_name, job_summary in wms_run_report.job_summary.items():
        fullname = f"{job.fullname}/{task_name}"
        wms_dict = {f"n_{wms_state_.name.lower()}": count_ for wms_state_, count_ in job_summary.items()}
        report: WmsTaskReport | None = None
        try:
            report = await WmsTaskReport.get_row_by_fullname(session, fullname)
            await report.update_values(session, **wms_dict)
        except Exception:
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
        except KeyError as msg:
            raise CMYamlParseError(f"Expecting PipetaskErrorType items not: {error_type_.keys()})") from msg

        new_error_type = await PipetaskErrorType.create_row(session, **val)
        ret_list.append(new_error_type)

    return ret_list
