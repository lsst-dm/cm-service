import os

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.ctrl.bps.wms_service import WmsRunReport

from ..db.campaign import Campaign
from ..db.group import Group
from ..db.job import Job
from ..db.pipetask_error import PipetaskError
from ..db.pipetask_error_type import PipetaskErrorType
from ..db.product_set import ProductSet
from ..db.script_template import ScriptTemplate
from ..db.specification import ScriptTemplateAssociation, SpecBlock, SpecBlockAssociation, Specification
from ..db.step import Step
from ..db.step_dependency import StepDependency
from ..db.task_set import TaskSet
from ..db.wms_task_report import WmsTaskReport


async def create_spec_block(
    session: async_scoped_session,
    config_values: dict,
    loaded_specs: dict,
) -> SpecBlock | None:
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
    include_data = {}
    for include_ in includes:
        if include_ in loaded_specs:
            include_data.update(loaded_specs[include_])
        else:
            spec_block_ = await SpecBlock.get_row_by_fullname(session, include_)
            include_data.update(
                handler=spec_block_.handler,
                data=spec_block_.data,
                collections=spec_block_.collections,
                child_config=spec_block_.child_config,
                scripts=spec_block_.scripts,
                spec_aliases=spec_block_.spec_aliases,
            )

    for include_key, include_val in include_data.items():
        if include_key not in block_data:
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
    )


async def create_script_template(
    session: async_scoped_session,
    config_values: dict,
) -> ScriptTemplate | None:
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

        for script_template_config_ in script_templates:
            new_script_template_assoc = await ScriptTemplateAssociation.create_row(
                session,
                spec_name=spec_name,
                **script_template_config_,
            )
            assert new_script_template_assoc
        for spec_block_config_ in spec_blocks:
            new_spec_block_assoc = await SpecBlockAssociation.create_row(
                session,
                spec_name=spec_name,
                **spec_block_config_,
            )
            assert new_spec_block_assoc
        await session.commit()
        return specification


async def load_specification(
    session: async_scoped_session,
    yaml_file: str,
    loaded_specs: dict | None = None,
) -> Specification | None:
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
            raise KeyError(f"Expecting one of {good_keys} not: {spec_data.keys()})")
    return specification


async def add_step_prerequisite(
    session: async_scoped_session,
    script_id: int,
    prereq_id: int,
) -> StepDependency:
    return await StepDependency.create_row(
        session,
        prereq_id=prereq_id,
        depend_id=script_id,
    )


async def add_steps(
    session: async_scoped_session,
    campaign: Campaign,
    child_configs: dict,
) -> Campaign:
    specification = await campaign.get_specification(session)
    spec_aliases = await campaign.get_spec_aliases(session)

    current_steps = await campaign.children(session)
    step_ids_dict = {step_.name: step_.id for step_ in current_steps}

    prereq_pairs = []
    for child_name_, child_config_ in child_configs.items():
        spec_block_name = child_config_.pop("spec_block")
        if spec_block_name is None:
            raise AttributeError(
                f"child_config_ {child_name_} of {campaign.fullname} does contain 'spec_block'",
            )
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        spec_block = await specification.get_block(session, spec_block_name)
        new_step = await Step.create_row(
            session,
            name=child_name_,
            spec_block_name=spec_block.fullname,
            parent_name=campaign.fullname,
            **child_config_,
        )
        await session.refresh(new_step)
        step_ids_dict[child_name_] = new_step.id
        prereqs_names = child_config_.pop("prerequisites", [])
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
    specification = await step.get_specification(session)
    spec_aliases = await step.get_spec_aliases(session)

    current_groups = await step.children(session)
    n_groups = len(list(current_groups))
    i = n_groups
    for child_name_, child_config_ in child_configs.items():
        spec_block_name = child_config_.pop("spec_block", None)
        if spec_block_name is None:
            raise AttributeError(f"child_config_ {child_name_} of {step.fullname} does contain 'spec_block'")
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        spec_block = await specification.get_block(session, spec_block_name)
        await Group.create_row(
            session,
            name=f"group{i}",
            spec_block_name=spec_block.fullname,
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
    for pipetask_error_type_ in await PipetaskErrorType.get_rows(session):
        if pipetask_error_type_.match(task_name, diagnostic_message):
            return pipetask_error_type_
    return None


async def load_manifest_report(
    session: async_scoped_session,
    job_name: str,
    yaml_file: str,
) -> Job:
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
            diagnostic_message = failed_quanta_data_["error"][-1]
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
    with open(yaml_file, encoding="utf-8") as fin:
        error_types = yaml.safe_load(fin)

    ret_list: list[PipetaskErrorType] = []
    for error_type_ in error_types:
        try:
            val = error_type_["PipetaskErrorType"]
        except KeyError as msg:
            raise KeyError(f"Expecting PipetaskErrorType items not: {error_type_.keys()})") from msg

        new_error_type = await PipetaskErrorType.create_row(session, **val)
        ret_list.append(new_error_type)

    return ret_list
