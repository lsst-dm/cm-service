from __future__ import annotations

import os
import shutil
import types
from functools import partial
from typing import TYPE_CHECKING, Any

import yaml
from anyio import Path, to_thread
from fastapi.concurrency import run_in_threadpool
from jinja2 import Environment, PackageLoader
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.ctrl.bps import BaseWmsService, WmsRunReport, WmsStates
from lsst.utils import doImport

from ..common.bash import parse_bps_stdout, write_bash_script
from ..common.butler import remove_run_collections
from ..common.enums import LevelEnum, StatusEnum, TaskStatusEnum, WmsMethodEnum
from ..common.errors import (
    CMBadExecutionMethodError,
    CMBadParameterTypeError,
    CMIDMismatchError,
    CMMissingScriptInputError,
    test_type_and_raise,
)
from ..common.logging import LOGGER
from ..config import config
from ..db.element import ElementMixin
from ..db.job import Job
from ..db.script import Script
from ..db.task_set import TaskSet
from ..db.wms_task_report import WmsTaskReport
from .functions import compute_job_status, load_manifest_report, load_wms_reports, status_from_bps_report
from .script_handler import FunctionHandler, ScriptHandler

WMS_TO_TASK_STATUS_MAP = {
    WmsStates.UNKNOWN: TaskStatusEnum.missing,
    WmsStates.MISFIT: TaskStatusEnum.missing,
    WmsStates.UNREADY: TaskStatusEnum.processing,
    WmsStates.READY: TaskStatusEnum.processing,
    WmsStates.PENDING: TaskStatusEnum.processing,
    WmsStates.RUNNING: TaskStatusEnum.processing,
    WmsStates.DELETED: TaskStatusEnum.failed,
    WmsStates.HELD: TaskStatusEnum.failed_upstream,
    WmsStates.SUCCEEDED: TaskStatusEnum.done,
    WmsStates.FAILED: TaskStatusEnum.failed,
    WmsStates.PRUNED: TaskStatusEnum.failed,
}

logger = LOGGER.bind(module=__name__)


class BpsScriptHandler(ScriptHandler):
    """Write a script to run bps jobs

    This will create:
    `parent.collections['run']`
    """

    wms_method = WmsMethodEnum.default

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        if TYPE_CHECKING:
            assert isinstance(parent, Job)
        # Database operations
        await session.refresh(parent, attribute_names=["c_"])
        data_dict = await script.data_dict(session)
        resolved_cols = await script.resolve_collections(session)

        # Resolve mandatory data element inputs. All of these values must be
        # provided somewhere along the SpecBlock chain.
        try:
            prod_area = os.path.expandvars(data_dict["prod_area"])
            butler_repo = os.path.expandvars(data_dict["butler_repo"])
            lsst_version = os.path.expandvars(data_dict["lsst_version"])
            lsst_distrib_dir = os.path.expandvars(data_dict["lsst_distrib_dir"])
            pipeline_yaml = os.path.expandvars(data_dict["pipeline_yaml"])
            run_coll = resolved_cols["run"]
            input_colls = resolved_cols["inputs"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        # workflow_config is the values dictionary to use while rendering a
        # yaml template, NOT the yaml template itself!
        workflow_config: dict[str, Any] = {}
        workflow_config["project"] = "DEFAULT"
        workflow_config["campaign"] = parent.c_.name
        workflow_config["pipeline_yaml"] = pipeline_yaml
        workflow_config["lsst_version"] = lsst_version
        workflow_config["lsst_distrib_dir"] = lsst_distrib_dir
        workflow_config["wms"] = self.wms_method.name
        workflow_config["script_method"] = script.run_method.name
        workflow_config["compute_site"] = data_dict.get("compute_site", self.default_compute_site.name)
        workflow_config["custom_lsst_setup"] = data_dict.get("custom_lsst_setup", None)
        workflow_config["extra_qgraph_options"] = data_dict.get("extra_qgraph_options", None)

        # Get the output file paths
        script_url = await self._set_script_files(session, script, prod_area)
        json_url = await Path(os.path.expandvars(f"{prod_area}/{script.fullname}_log.json")).resolve()
        config_url = await Path(
            os.path.expandvars(f"{prod_area}/{script.fullname}_bps_config.yaml")
        ).resolve()
        log_url = await Path(os.path.expandvars(f"{prod_area}/{script.fullname}.log")).resolve()
        config_path = await Path(config_url).resolve()
        submit_path = await Path(f"{prod_area}/{parent.fullname}/submit").resolve()
        workflow_config["submit_path"] = str(submit_path)

        try:
            await run_in_threadpool(shutil.rmtree, submit_path)
        except FileNotFoundError:
            pass

        command = f"{config.bps.bps_bin} --log-file {json_url} --no-log-tty submit {config_path} > {log_url}"
        await write_bash_script(script_url, command, values=workflow_config)

        # FIXME at this point, how could the following path *not* exist?
        #       is this meant to be `config_url` instead?
        await Path(script_url).parent.mkdir(parents=True, exist_ok=True)

        workflow_config["extra_yaml_literals"] = []
        include_configs = []

        # FIXME `bps_wms_*_file` should be added to the generic list of
        # `bps_wms_extra_files` instead of being specific keywords. The only
        # reason they are kept separate is to support overrides of their
        # specific role
        bps_wms_extra_files = data_dict.get("bps_wms_extra_files", [])
        bps_wms_clustering_file = data_dict.get("bps_wms_clustering_file", None)
        bps_wms_resources_file = data_dict.get("bps_wms_resources_file", None)
        bps_wms_yaml_file = data_dict.get("bps_wms_yaml_file", None)
        for to_include_ in [
            bps_wms_yaml_file,
            bps_wms_clustering_file,
            bps_wms_resources_file,
            *bps_wms_extra_files,
        ]:
            if to_include_:
                # We want abspaths, but we need to be careful about
                # envvars that are not yet expanded
                to_include_ = os.path.expandvars(to_include_)
                # If the potential include file has an unexpanded env var, we
                # delegate that expansion to the bps runtime, since it may
                # refer to a stack env var we do not understand.
                if "$" in to_include_:
                    include_configs.append(str(to_include_))
                    continue

                # Otherwise, instead of including it we should render it out
                # because it's a path we understand but the bps runtime won't
                to_include_ = await Path(to_include_).resolve()

                try:
                    include_yaml_ = yaml.dump(yaml.safe_load(await to_include_.read_text()))
                    workflow_config["extra_yaml_literals"].append(include_yaml_)
                except yaml.YAMLError:
                    logger.exception()
                    raise

        workflow_config["include_configs"] = include_configs

        if isinstance(input_colls, list):  # pragma: no cover
            in_collection = ",".join(input_colls)
        else:
            in_collection = input_colls

        payload = {
            "name": parent.c_.name,
            "butler_config": butler_repo,
            "output_run_collection": run_coll,
            "input_collection": in_collection,
            "data_query": data_dict.get("data_query", None),
        }
        if data_dict.get("rescue", False):  # pragma: no cover
            skip_colls = data_dict.get("skip_colls", "")
            payload["extra_args"] = f"--skip-existing-in {skip_colls}"

        workflow_config["payload"] = payload

        # Get the yaml template using package lookup
        config_template_environment = Environment(loader=PackageLoader("lsst.cmservice"))
        config_template = config_template_environment.get_template("bps_submit_yaml.j2")
        try:
            # Render bps_submit_yaml template to `config_url`
            yaml_output = config_template.render(workflow_config)
            await Path(config_url).write_text(yaml_output)
        except yaml.YAMLError as yaml_error:
            raise yaml.YAMLError(f"Error writing a script to run BPS job {script}; threw {yaml_error}")
        return StatusEnum.prepared

    async def _check_slurm_job(
        self,
        session: async_scoped_session,
        slurm_id: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        fake_status = fake_status or config.mock_status
        slurm_status = await ScriptHandler._check_slurm_job(
            self,
            session,
            slurm_id,
            script,
            parent,
            fake_status,
        )
        await script.update_values(session, status=slurm_status)
        if slurm_status not in [StatusEnum.reviewable, StatusEnum.accepted]:  # pragma: no cover
            return slurm_status
        if fake_status is not None:
            wms_job_id = "fake_job"
        else:  # pragma: no cover
            if TYPE_CHECKING:
                assert script.log_url is not None
            bps_dict = await parse_bps_stdout(script.log_url)
            wms_job_id = self.get_job_id(bps_dict)
        await parent.update_values(session, wms_job_id=wms_job_id)
        return slurm_status

    async def _check_htcondor_job(
        self,
        session: async_scoped_session,
        htcondor_id: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        fake_status = fake_status or config.mock_status
        htcondor_status = await ScriptHandler._check_htcondor_job(
            self,
            session,
            htcondor_id,
            script,
            parent,
            fake_status,
        )
        if htcondor_status in [StatusEnum.reviewable, StatusEnum.accepted]:
            await script.update_values(session, status=htcondor_status)
            if fake_status is not None:
                wms_job_id = "fake_job"
            else:  # pragma: no cover
                if TYPE_CHECKING:
                    assert script.log_url is not None
                bps_dict = await parse_bps_stdout(script.log_url)
                wms_job_id = self.get_job_id(bps_dict)
            await parent.update_values(session, wms_job_id=wms_job_id)
        return htcondor_status

    async def launch(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        test_type_and_raise(parent, Job, "BpsScriptHandler parent")
        status = await ScriptHandler.launch(self, session, script, parent, **kwargs)
        await parent.update_values(session, stamp_url=script.stamp_url)
        return status

    @classmethod
    def get_job_id(cls, bps_dict: dict) -> str:
        raise NotImplementedError

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        update_fields = await ScriptHandler._reset_script(
            self, session, script, to_status, fake_reset=fake_reset
        )
        if to_status == StatusEnum.prepared:
            return update_fields
        if script.script_url is None:  # pragma: no cover
            return update_fields
        json_url = script.script_url.replace(".sh", "_log.json")
        config_url = script.script_url.replace(".sh", "_bps_config.yaml")
        submit_path = script.script_url.replace(
            os.path.basename(script.script_url),
            "/submit",
        )

        await Path(json_url).unlink(missing_ok=True)
        await Path(config_url).unlink(missing_ok=True)
        try:
            await run_in_threadpool(shutil.rmtree, submit_path)
        except FileNotFoundError:  # pragma: no cover
            pass
        return update_fields

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            run_coll = resolved_cols["run"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_run_collections(butler_repo, run_coll, fake_reset=fake_reset)


class BpsReportHandler(FunctionHandler):
    """Class to handle running BpsReport"""

    wms_svc_class_name: str | None = None

    def __init__(self, spec_block_id: int, **kwargs: dict) -> None:
        FunctionHandler.__init__(self, spec_block_id, **kwargs)
        self._wms_svc_class: types.ModuleType | type | None = None
        self._wms_svc: BaseWmsService | None = None

    def _get_wms_svc(self, **kwargs: Any) -> BaseWmsService | None:
        # FIXME this should happen in __init__
        if self.wms_svc_class_name is None:  # pragma: no cover
            raise CMBadExecutionMethodError(f"{type(self)} should not be used, use a sub-class instead")

        try:
            self._wms_svc_class = doImport(self.wms_svc_class_name)
        except ImportError:
            logger.exception()
            # This may not be an error when under testing
            return None

        if self._wms_svc is None:
            if isinstance(self._wms_svc_class, types.ModuleType):  # pragma: no cover
                raise CMBadExecutionMethodError(
                    f"Site class={self.wms_svc_class_name} is not a BaseWmsService subclass",
                )
            self._wms_svc = self._wms_svc_class(kwargs)
        return self._wms_svc

    async def _load_wms_reports(
        self,
        session: async_scoped_session,
        job: Job,
        wms_workflow_id: str | None,
        **kwargs: Any,
    ) -> StatusEnum | None:
        """Load the job processing info

        Parameters
        ---------
        job: Job
            Job in question

        wms_workflow_id : str | None
            WMS workflow id

        Returns
        -------
        status: StatusEnum | None
            Status of requested job
        """
        fake_status = kwargs.get("fake_status", config.mock_status)
        wms_svc = self._get_wms_svc(config={})

        # It is an error if the wms_svc_class cannot be imported when not under
        # a fake status.
        if all([wms_svc is None, fake_status is None]):
            raise ImportError

        # Return early with fake status or a missing wf id
        elif any([wms_workflow_id is None, fake_status is not None]):
            return status_from_bps_report(None, fake_status=fake_status)

        if TYPE_CHECKING:
            assert wms_svc is not None
            assert wms_workflow_id is not None
            run_reports: list[WmsRunReport]
            wms_run_report: WmsRunReport | None

        try:
            # FIXME: Why does wms_workflow_id need to be stripped?
            wms_svc_report = partial(wms_svc.report, wms_workflow_id=wms_workflow_id.strip())
            run_reports, message = await to_thread.run_sync(wms_svc_report)
            logger.debug(message)
            wms_run_report = run_reports[0]
            _ = await load_wms_reports(session, job, wms_run_report)
            status = status_from_bps_report(wms_run_report)
        except Exception:
            # FIXME setting status failed for any exception seems extreme,
            #       there should be *retryable* exceptions with some kind of
            #       backoff
            logger.exception()
            status = StatusEnum.failed
        return status

    async def _do_prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin | Job,
        **kwargs: Any,
    ) -> StatusEnum:
        if TYPE_CHECKING:
            assert type(parent) is Job

        await script.update_values(
            session,
            stamp_url=parent.wms_job_id,
        )
        return StatusEnum.prepared

    async def _do_check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin | Job,
        **kwargs: Any,
    ) -> StatusEnum:
        if TYPE_CHECKING:
            assert type(parent) is Job

        fake_status = kwargs.get("fake_status", None)
        status = await self._load_wms_reports(session, parent, parent.wms_job_id, fake_status=fake_status)
        status = script.status if status is None else status
        await script.update_values(session, status=status)
        return status

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        update_fields = await FunctionHandler._reset_script(
            self, session, script, to_status, fake_reset=fake_reset
        )
        parent: ElementMixin | Job = await script.get_parent(session)

        if TYPE_CHECKING:
            assert type(parent) is Job

        if parent.level != LevelEnum.job:  # pragma: no cover
            raise CMBadParameterTypeError(f"Script parent is a {parent.level}, not a LevelEnum.job")
        await session.refresh(parent, attribute_names=["wms_reports_"])
        for wms_report_ in parent.wms_reports_:
            await WmsTaskReport.delete_row(session, wms_report_.id)
        return update_fields


class PandaScriptHandler(BpsScriptHandler):
    """Class to handle running Bps for panda jobs"""

    wms_method = WmsMethodEnum.panda

    @classmethod
    def get_job_id(cls, bps_dict: dict) -> str:
        return bps_dict["Run Id"]


class HTCondorScriptHandler(BpsScriptHandler):
    """Class to handle running Bps for ht_condor jobs"""

    wms_method = WmsMethodEnum.htcondor

    @classmethod
    def get_job_id(cls, bps_dict: dict) -> str:
        return bps_dict["Submit dir"]


class PandaReportHandler(BpsReportHandler):
    """Class to handle running BpsReport for panda jobs"""

    wms_svc_class_name = "lsst.ctrl.bps.panda.PanDAService"


class HTCondorReportHandler(BpsReportHandler):
    """Class to handle running BpsReport for ht_condor jobs"""

    wms_svc_class_name = "lsst.ctrl.bps.htcondor.HTCondorService"


class ManifestReportScriptHandler(ScriptHandler):
    """Write a script to run manifest checker jobs"""

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        script_url = await self._set_script_files(session, script, prod_area)
        butler_repo = data_dict["butler_repo"]
        job_run_coll = resolved_cols["job_run"]
        qgraph_file = f"{job_run_coll}.qgraph".replace("/", "_")

        graph_url = await Path(f"{prod_area}/{parent.fullname}/submit/{qgraph_file}").resolve()
        report_url = await Path(f"{prod_area}/{parent.fullname}/submit/manifest_report.yaml").resolve()

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        command = (
            f"{config.bps.pipetask_bin} report --full-output-filename {report_url} {butler_repo} {graph_url}"
        )
        await write_bash_script(script_url, command, values=template_values)

        return StatusEnum.prepared


class ManifestReportLoadHandler(FunctionHandler):
    """Class to load the Manifest check report"""

    async def _do_prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        report_url = os.path.expandvars(f"{prod_area}/{parent.fullname}/submit/manifest_report.yaml")

        await script.update_values(
            session,
            stamp_url=report_url,
        )
        return StatusEnum.prepared

    async def _do_check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin | Job,
        **kwargs: Any,
    ) -> StatusEnum:
        if TYPE_CHECKING:
            assert type(parent) is Job
            assert script.stamp_url is not None

        fake_status = kwargs.get("fake_status", config.mock_status)
        status = await self._load_pipetask_report(session, parent, script.stamp_url, fake_status=fake_status)
        status = status if fake_status is None else fake_status
        await script.update_values(session, status=status)
        return status

    async def _load_pipetask_report(
        self,
        session: async_scoped_session,
        job: Job,
        pipetask_report_yaml: str,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        """Load the job processing info

        Paramters
        ---------
        job: Job
            Job in question

        pipetask_report_yaml : str | None
            Yaml file

        """
        check_job = await load_manifest_report(
            session, job.fullname, pipetask_report_yaml, fake_status=fake_status
        )
        if not job.id == check_job.id:  # pragma: no cover
            raise CMIDMismatchError(f"job.id {job.id} != check_job.id {check_job.id}")

        status = await compute_job_status(session, job)
        return status

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        update_fields = await FunctionHandler._reset_script(
            self, session, script, to_status, fake_reset=fake_reset
        )
        parent = await script.get_parent(session)

        if TYPE_CHECKING:
            assert type(parent) is Job

        if parent.level != LevelEnum.job:  # pragma: no cover
            raise CMBadParameterTypeError(f"Script parent is a {parent.level}, not a LevelEnum.job")
        await session.refresh(parent, attribute_names=["tasks_"])
        for task_ in parent.tasks_:
            await TaskSet.delete_row(session, task_.id)
        return update_fields
