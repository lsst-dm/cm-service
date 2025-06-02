import os
from collections import deque
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

import yaml
from anyio import Path
from pydantic.v1.utils import deep_update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.ctrl.bps.bps_reports import compile_job_summary
from lsst.ctrl.bps.wms_service import WmsRunReport, WmsStates

from ..common.enums import StatusEnum
from ..common.errors import CMMissingFullnameError, CMYamlParseError
from ..common.logging import LOGGER
from ..config import config
from ..db.campaign import Campaign
from ..db.job import Job
from ..db.pipetask_error import PipetaskError
from ..db.pipetask_error_type import PipetaskErrorType
from ..db.product_set import ProductSet
from ..db.spec_block import SpecBlock
from ..db.specification import Specification
from ..db.step import Step
from ..db.step_dependency import StepDependency
from ..db.task_set import TaskSet
from ..db.wms_task_report import WmsTaskReport

logger = LOGGER.bind(module=__name__)


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
    key = config_values["name"]
    loaded_specs[key] = config_values
    spec_block_q = select(SpecBlock).where(SpecBlock.fullname == key)
    spec_block_result = await session.scalars(spec_block_q)
    spec_block = spec_block_result.first()
    if spec_block and not allow_update:
        print(f"SpecBlock {key} already defined, leaving it unchanged")
        return spec_block
    includes = config_values.get("includes", [])
    block_data = config_values.copy()
    include_data: dict[str, Any] = {}
    for include_ in includes:
        if include_ in loaded_specs:
            include_data = deep_update(include_data, loaded_specs[include_])
        else:  # pragma: no cover
            # This is only needed if the block are in reverse dependency order
            # in the specification yaml file
            spec_block_ = await SpecBlock.get_row_by_fullname(session, include_)
            include_data = deep_update(
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
        Values for the Specification

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
    yaml_file: str | Path | deque,
    loaded_specs: dict | None = None,
    *,
    allow_update: bool = False,
) -> Specification:
    """Load Specification, and SpecBlock objects from a yaml
    file, including from files referenced by Include blocks. Return the last
    Specification object in the file.

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    yaml_file: str | anyio.Path
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
    specification = None

    if loaded_specs is None:  # pragma: no cover
        loaded_specs = {}

    if isinstance(yaml_file, deque):
        spec_data = yaml_file
    else:
        yaml_file = Path(yaml_file)
        if not await yaml_file.exists():
            raise CMYamlParseError(f"Specification does not exist at path {yaml_file}")
        spec_yaml = await yaml_file.read_bytes()
        try:
            spec_data = deque()
            spec_batches = yaml.safe_load_all(spec_yaml)
            for spec in spec_batches:
                spec_data += spec
        except yaml.YAMLError as yaml_error:
            raise CMYamlParseError(
                f"Error parsing specification {yaml_file}; threw {yaml_error}"
            ) from yaml_error
        except Exception as e:
            raise CMYamlParseError(f"{e}") from e

    while spec_data:
        config_item = spec_data.popleft()
        if "Imports" in config_item:
            imports = config_item["Imports"]
            for import_ in imports:
                import_yaml = await Path(os.path.abspath(os.path.expandvars(import_))).read_bytes()
                for import_item in yaml.safe_load(import_yaml):
                    spec_data.appendleft(import_item)
        elif "SpecBlock" in config_item:
            try:
                await upsert_spec_block(
                    session,
                    config_item["SpecBlock"],
                    loaded_specs,
                    allow_update=allow_update,
                )
            except CMMissingFullnameError:
                # move this item to the end of the list to try again later
                # TODO prevent infinite loops for genuinely bad inputs
                spec_data.append(config_item)
        elif "Specification" in config_item:
            specification = await upsert_specification(
                session,
                config_item["Specification"],
                allow_update=allow_update,
            )
        else:  # pragma: no cover
            logger.warning(
                "Some spec blocks were not loaded from unexpected keys",
                expected_keys="SpecBlock | Specification | Imports",
                config_item=config_item,
            )

    if specification is None:
        raise ValueError("load_specification() did not return a Specification")
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

    if TYPE_CHECKING:
        assert isinstance(campaign.data, dict)

    if campaign.data.get("namespace"):
        campaign_namespace = UUID(campaign.data.get("namespace"))
    else:
        campaign_namespace = None

    prereq_pairs = []
    for step_ in step_config_list:
        try:
            step_config_ = step_["Step"]
        except KeyError as msg:
            raise CMYamlParseError(f"Expecting Step not: {step_.keys()}") from msg
        child_name_ = step_config_.pop("name")
        spec_block_name = step_config_.pop("spec_block")

        if spec_block_name is None:  # pragma: no cover
            raise CMYamlParseError(
                f"Step {child_name_} of {campaign.fullname} does contain 'spec_block'",
            )

        namespaced_step_name = (
            str(uuid5(campaign_namespace, child_name_)) if campaign_namespace else child_name_
        )
        namespaced_spec_block_name = (
            str(uuid5(campaign_namespace, spec_block_name)) if campaign_namespace else spec_block_name
        )

        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        step_config_ = deep_update(step_config_, child_config.get(child_name_, {}))

        new_step = await Step.create_row(
            session,
            name=namespaced_step_name,
            spec_block_name=namespaced_spec_block_name,
            original_name=child_name_,
            parent_name=campaign.fullname,
            **step_config_,
        )
        await session.refresh(new_step)
        step_ids_dict[namespaced_step_name] = new_step.id

        prereq_list = [
            str(uuid5(campaign_namespace, prereq)) if campaign_namespace else prereq
            for prereq in step_config_.pop("prerequisites", [])
        ]
        prereq_pairs += [(namespaced_step_name, prereq) for prereq in prereq_list]

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
    yaml_file: str | Path,
    fake_status: StatusEnum | None = None,
    *,
    allow_update: bool = False,
) -> Job:
    """Parse and load output of pipetask report

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    job_name: str
        Name of associated Job

    yaml_file: str | anyio.Path
        Pipetask report yaml file

    fake_status: StatusEnum | None
        If set, return this status

    allow_update: bool
        If set, allow updating values

    Returns
    -------
    job : Job
        Associated Job
    """
    job = await Job.get_row_by_fullname(session, job_name)
    fake_status = fake_status or config.mock_status
    yaml_file = Path(yaml_file)
    if fake_status is not None:
        return job
    if not await yaml_file.exists():
        raise CMYamlParseError(f"Manifest report yaml does not exist at path {yaml_file}")
    try:
        manifest_yaml = await yaml_file.read_bytes()
        manifest_data = yaml.safe_load(manifest_yaml)
    except yaml.YAMLError as yaml_error:
        raise CMYamlParseError(
            f"Error parsing manifest report yaml at path {yaml_file}; threw {yaml_error}"
        ) from yaml_error
    except Exception as e:
        raise CMYamlParseError(f"{e}") from e
    for task_name_, task_data_ in manifest_data.items():
        failed_quanta = task_data_.get("failed_quanta", {})
        outputs = task_data_.get("outputs", {})
        n_expected = task_data_.get("n_expected", 0)
        n_failed = len(failed_quanta)
        n_failed_upstream = task_data_.get("n_quanta_blocked", 0)
        n_done = task_data_.get("n_succeeded", 0)

        task_fullname = f"{job_name}/{task_name_}"
        try:
            task_set = await TaskSet.get_row_by_fullname(session, task_fullname)
            if allow_update:
                task_set = await TaskSet.update_row(
                    session,
                    row_id=task_set.id,
                    job_id=job.id,
                    name=task_name_,
                    fullname=task_fullname,
                    n_expected=n_expected,
                    n_done=n_done,
                )
        except CMMissingFullnameError:
            task_set = await TaskSet.create_row(
                session,
                job_id=job.id,
                name=task_name_,
                fullname=task_fullname,
                n_expected=n_expected,
                n_done=n_done,
                n_failed=n_failed,
                n_failed_upstream=n_failed_upstream,
            )

        for data_type_, counts_ in outputs.items():
            product_fullname = f"{task_set.fullname}/{data_type_}"
            try:
                product_set = await ProductSet.get_row_by_fullname(
                    session,
                    product_fullname,
                )
                if allow_update:
                    product_set = await ProductSet.update_row(
                        session,
                        row_id=product_set.id,
                        job_id=job.id,
                        task_id=task_set.id,
                        name=data_type_,
                        fullname=product_fullname,
                        n_expected=counts_.get("expected", 0),
                        n_done=counts_.get("produced", 0),
                        n_failed=counts_.get("failed", 0),
                        n_failed_upstream=counts_.get("blocked", 0),
                        n_missing=counts_.get("not_produced", 0),
                    )
            except CMMissingFullnameError:
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

        for failed_quanta_uuid_, failed_quanta_data_ in failed_quanta.items():
            diagnostic_message_list = failed_quanta_data_["error"]
            if diagnostic_message_list:
                diagnostic_message = diagnostic_message_list[-1]
            else:  # pragma: no cover
                diagnostic_message = "Super-unhelpful empty message"

            error_type = await match_pipetask_error(
                session,
                task_name_,
                diagnostic_message,
            )

            error_type_id = error_type.id if error_type is not None else None
            try:
                pipetask_error = await PipetaskError.get_row_by_fullname(
                    session,
                    failed_quanta_uuid_,
                )
                if allow_update:
                    pipetask_error = await PipetaskError.update_row(
                        session,
                        row_id=pipetask_error.id,
                        error_type_id=error_type_id,
                        task_id=task_set.id,
                        quanta=failed_quanta_uuid_,
                        data_id=failed_quanta_data_["data_id"],
                        diagnostic_message=diagnostic_message,
                    )
            except CMMissingFullnameError:
                pipetask_error = await PipetaskError.create_row(
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
    fake_status: StatusEnum | None = None,
) -> StatusEnum:
    """Decide the status for a workflow for a bps report

    Parameters
    ----------
    wms_run_report: WmsRunReport,
        bps report return object

    campaign: str | None
        The name of the campaign to which the bps report is relevant

    job: str | None
        The name of the job to which the bps report is relevant

    Returns
    -------
    status: StatusEnum
        The status to set for the bps_report script
    """
    # FIXME: this function must communicate more explicitly the conditions it
    # discovers. The APIs for obtaining wms status are lacking in filtering
    # capabilities and the CLI doesn't have good tools for showing the status
    # of a task.
    if wms_run_report is None:
        return fake_status or config.mock_status or StatusEnum.accepted

    the_state = wms_run_report.state
    logger.debug("Deriving status from BPS report", status=the_state)

    # If any of the jobs are in a HELD state, this requires intervention
    # and a notification should be sent and A BLOCKED status returned
    for blocked_job in filter(lambda x: x.state in [WmsStates.HELD], wms_run_report.jobs):
        return StatusEnum.blocked
    if the_state == WmsStates.RUNNING:
        return StatusEnum.running
    elif the_state == WmsStates.SUCCEEDED:
        return StatusEnum.accepted
    elif the_state in [
        WmsStates.UNKNOWN,
        WmsStates.MISFIT,
        WmsStates.PRUNED,
        WmsStates.UNREADY,
        WmsStates.READY,
        WmsStates.HELD,
        WmsStates.PENDING,
    ]:
        return StatusEnum.failed

    for final_job in filter(lambda x: x.name == "finalJob", wms_run_report.jobs):
        if final_job.state == WmsStates.SUCCEEDED:
            # we want downstream scripts, e..g, pipetask report, to run
            return StatusEnum.accepted
        # There should only ever be one finalJob but to prevent weird loops
        break

    # In any cases not previously handled, return a reviewable status
    return StatusEnum.reviewable


async def load_wms_reports(
    session: async_scoped_session,
    job: Job,
    wms_run_report: WmsRunReport | None,
) -> Job:  # pragma: no cover
    """Parse and load output of bps report

    FIXME: add to coverage

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
        compile_job_summary(wms_run_report)
        if wms_run_report.job_summary is None:
            raise RuntimeError("compile_job_summary did not compile a job summary")
    for task_name, job_summary in wms_run_report.job_summary.items():
        fullname = f"{job.fullname}/{task_name}"
        wms_dict = {f"n_{wms_state_.name.lower()}": count_ for wms_state_, count_ in job_summary.items()}
        report: WmsTaskReport | None = None
        try:
            report = await WmsTaskReport.get_row_by_fullname(session, fullname)
            await report.update_values(session, **wms_dict)
        except CMMissingFullnameError:
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
    yaml_file: str | Path,
) -> list[PipetaskErrorType]:
    """Parse and load error types

    Parameters
    ----------
    session: async_scoped_session
        DB session manager

    yaml_file: str | anyio.Path
        Error type definition yaml file

    Returns
    -------
    error_types : list[PipetaskErrorType]
        Newly loaded error types
    """
    yaml_file = Path(yaml_file)
    if not await yaml_file.exists():
        raise CMYamlParseError(f"Error type yaml does not exist at path {yaml_file}")
    try:
        error_yaml = await yaml_file.read_bytes()
        error_types = yaml.safe_load(error_yaml)
    except yaml.YAMLError as yaml_error:
        raise CMYamlParseError(
            f"Error parsing error type yaml at path {yaml_file}; threw {yaml_error}"
        ) from yaml_error
    except Exception as e:
        raise CMYamlParseError(f"{e}") from e

    ret_list: list[PipetaskErrorType] = []
    for error_type_ in error_types:
        try:
            val = error_type_["PipetaskErrorType"]
        except KeyError as msg:
            raise CMYamlParseError(f"Expecting PipetaskErrorType items not: {error_type_.keys()})") from msg

        val["diagnostic_message"] = val["diagnostic_message"].strip()
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
