from __future__ import annotations

import contextlib
import os
import types
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.common.bash import write_bash_script
from lsst.cmservice.db.element import ElementMixin
from lsst.cmservice.db.job import Job
from lsst.cmservice.db.script import Script
from lsst.cmservice.db.task_set import TaskSet
from lsst.cmservice.db.wms_task_report import WmsTaskReport
from lsst.ctrl.bps import BaseWmsService, WmsStates
from lsst.utils import doImport

from ..common.bash import parse_bps_stdout
from ..common.butler import remove_run_collections
from ..common.enums import LevelEnum, StatusEnum, TaskStatusEnum, WmsMethodEnum
from ..common.errors import (
    CMBadExecutionMethodError,
    CMBadParameterTypeError,
    CMIDMismatchError,
    CMMissingScriptInputError,
)
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


class BpsScriptHandler(ScriptHandler):
    """Write a script to run bps jobs

    This will create:
    `parent.collections['run']`
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        specification = await script.get_specification(session)
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            prod_area = os.path.expandvars(data_dict["prod_area"])
            butler_repo = os.path.expandvars(data_dict["butler_repo"])
            lsst_version = os.path.expandvars(data_dict["lsst_version"])
            lsst_distrib_dir = os.path.expandvars(data_dict["lsst_distrib_dir"])
            pipeline_yaml = os.path.expandvars(data_dict["pipeline_yaml"])
            run_coll = resolved_cols["run"]
            input_colls = resolved_cols["inputs"]
            bps_core_yaml_template = data_dict["bps_core_yaml_template"]
            bps_core_script_template = data_dict["bps_core_script_template"]
            bps_wms_script_template = data_dict["bps_wms_script_template"]
        except KeyError as msg:  # pragma: no cover
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        script_url = await self._set_script_files(session, script, prod_area)

        # optional stuff from data_dict
        rescue = data_dict.get("rescue", False)
        skip_colls = data_dict.get("skip_colls", "")
        custom_lsst_setup = data_dict.get("custom_lsst_setup", None)
        bps_wms_yaml_file = data_dict.get("bps_wms_yaml_file", None)
        bps_wms_clustering_file = data_dict.get("bps_wms_clustering_file", None)
        bps_wms_resources_file = data_dict.get("bps_wms_resources_file", None)
        bps_wms_extra_files = data_dict.get("bps_wms_extra_files", [])
        bps_extra_config = data_dict.get("bps_extra_config", None)
        data_query = data_dict.get("data_query", None)
        extra_qgraph_options = data_dict.get("extra_qgraph_options", None)

        # Get the output file paths
        script_url = await self._set_script_files(session, script, prod_area)
        json_url = os.path.abspath(os.path.expandvars(f"{prod_area}/{script.fullname}_log.json"))
        config_url = os.path.abspath(os.path.expandvars(f"{prod_area}/{script.fullname}_bps_config.yaml"))
        log_url = os.path.abspath(os.path.expandvars(f"{prod_area}/{script.fullname}.log"))

        # get the requested templates
        bps_core_script_template_ = await specification.get_script_template(
            session,
            bps_core_script_template,
        )
        bps_core_yaml_template_ = await specification.get_script_template(
            session,
            bps_core_yaml_template,
        )
        bps_wms_script_template_ = await specification.get_script_template(
            session,
            bps_wms_script_template,
        )

        submit_path = os.path.abspath(f"{prod_area}/{parent.fullname}/submit")
        try:
            os.rmdir(submit_path)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        # build up the bps wrapper script
        command = f"bps --log-file {json_url} --no-log-tty submit {os.path.abspath(config_url)} > {log_url}"

        prepend = bps_core_script_template_.data["text"].replace("{lsst_version}", lsst_version)
        prepend = prepend.replace("{lsst_distrib_dir}", lsst_distrib_dir)
        # Add custom_lsst_setup to the bps submit script
        # in case it is a change to bps itself
        if custom_lsst_setup:  # pragma: no cover
            prepend += f"\n{custom_lsst_setup}\n"
        prepend += bps_wms_script_template_.data["text"]

        write_bash_script(script_url, command, prepend=prepend)

        workflow_config = bps_core_yaml_template_.data.copy()

        include_configs = []
        for to_include_ in [bps_wms_yaml_file, bps_wms_clustering_file, bps_wms_resources_file]:
            if to_include_:
                # We want abspaths, but we need to be careful about
                # envvars that are not yet expanded
                to_include_ = os.path.expandvars(to_include_)
                if "$" not in to_include_:
                    to_include_ = os.path.abspath(to_include_)
                include_configs.append(to_include_)
        include_configs += bps_wms_extra_files

        workflow_config["includeConfigs"] = include_configs

        await session.refresh(parent, attribute_names=["c_", "p_"])
        workflow_config["project"] = parent.p_.name
        workflow_config["campaign"] = parent.c_.name

        workflow_config["submitPath"] = submit_path

        workflow_config["LSST_VERSION"] = os.path.expandvars(lsst_version)
        if custom_lsst_setup:  # pragma: no cover
            workflow_config["custom_lsst_setup"] = custom_lsst_setup
        workflow_config["pipelineYaml"] = pipeline_yaml

        if extra_qgraph_options:  # pragma: no cover
            workflow_config["extraQgraphOptions"] = extra_qgraph_options.replace("\n", " ").strip()

        if isinstance(input_colls, list):  # pragma: no cover
            in_collection = ",".join(input_colls)
        else:
            in_collection = input_colls

        payload = {
            "payloadName": parent.c_.name,
            "butlerConfig": butler_repo,
            "outputRun": run_coll,
            "inCollection": in_collection,
        }
        if data_query:
            payload["dataQuery"] = data_query.replace("\n", " ").strip()
        if rescue:  # pragma: no cover
            payload["extra_args"] = f"--skip-existing-in {skip_colls}"

        workflow_config["payload"] = payload

        if bps_extra_config:  # pragma: no cover
            workflow_config.update(**bps_extra_config)

        with contextlib.suppress(OSError):
            os.makedirs(os.path.dirname(script_url))

        with open(config_url, "w", encoding="utf-8") as fout:
            yaml.dump(workflow_config, fout)
        return StatusEnum.prepared

    async def _check_slurm_job(
        self,
        session: async_scoped_session,
        slurm_id: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        slurm_status = await ScriptHandler._check_slurm_job(
            self,
            session,
            slurm_id,
            script,
            parent,
            fake_status,
        )
        if slurm_status in [StatusEnum.reviewable, StatusEnum.accepted]:
            await script.update_values(session, status=slurm_status)
            if fake_status is not None:
                wms_job_id = "fake_job"
            else:  # pragma: no cover
                bps_dict = parse_bps_stdout(script.log_url)
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
                bps_dict = parse_bps_stdout(script.log_url)
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
        if not isinstance(parent, Job):  # pragma: no cover
            raise CMBadExecutionMethodError(f"Script {script} should not be run on {parent}")

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
        if script.script_url and to_status.value <= StatusEnum.ready.value:
            json_url = script.script_url.replace(".sh", "_log.json")
            config_url = script.script_url.replace(".sh", "_bps_config.yaml")
            submit_path = script.script_url.replace(
                os.path.basename(script.script_url),
                "/submit",
            )
            try:
                os.unlink(json_url)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            try:
                os.unlink(config_url)
            except Exception:  # pragma: no cover
                pass
            try:
                os.rmdir(submit_path)
            except Exception:  # pylint: disable=broad-exception-caught
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
        except KeyError as msg:  # pragma: no cover
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        remove_run_collections(butler_repo, run_coll, fake_reset=fake_reset)


class BpsReportHandler(FunctionHandler):
    """Class to handle running BpsReport"""

    wms_svc_class_name: str | None = None

    def __init__(self, spec_block_id: int, **kwargs: dict) -> None:
        FunctionHandler.__init__(self, spec_block_id, **kwargs)
        self._wms_svc_class: types.ModuleType | type | None = None
        self._wms_svc: BaseWmsService | None = None

    def _get_wms_svc(self, **kwargs: Any) -> BaseWmsService:
        if self._wms_svc is None:
            if self.wms_svc_class_name is None:  # pragma: no cover
                raise CMBadExecutionMethodError(f"{type(self)} should not be used, use a sub-class instead")
            self._wms_svc_class = doImport(self.wms_svc_class_name)
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

        Paramters
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
        fake_status = kwargs.get("fake_status", None)

        try:
            wms_svc = self._get_wms_svc()
        except ImportError as msg:
            if not fake_status:  # pragma: no cover
                raise msg
        try:
            if fake_status or wms_workflow_id is None:
                wms_run_report = None
            else:  # pragma: no cover
                wms_run_report = wms_svc.report(wms_workflow_id=wms_workflow_id.strip())[0][0]
            _job = await load_wms_reports(session, job, wms_run_report)
            status = status_from_bps_report(wms_run_report, fake_status=fake_status)
        except Exception as msg:  # pragma: no cover
            print(f"Catching wms_svc.report failure: {msg}, continuing")
            status = StatusEnum.failed
        return status

    async def _do_prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        await script.update_values(
            session,
            stamp_url=parent.wms_job_id,
        )
        return StatusEnum.prepared

    async def _do_check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
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
        parent = await script.get_parent(session)
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

    wms_method = WmsMethodEnum.ht_condor

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
        specification = await script.get_specification(session)
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        script_url = await self._set_script_files(session, script, prod_area)
        butler_repo = data_dict["butler_repo"]
        lsst_distrib_dir = data_dict["lsst_distrib_dir"]
        lsst_version = data_dict["lsst_version"]
        job_run_coll = resolved_cols["job_run"]
        qgraph_file = f"{job_run_coll}.qgraph".replace("/", "_")

        graph_url = os.path.abspath(f"{prod_area}/{parent.fullname}/submit/{qgraph_file}")
        report_url = os.path.abspath(f"{prod_area}/{parent.fullname}/submit/manifest_report.yaml")

        manifest_script_template = await specification.get_script_template(
            session,
            data_dict["manifest_script_template"],
        )
        prepend = manifest_script_template.data["text"].replace("{lsst_version}", lsst_version)
        prepend = prepend.replace("{lsst_distrib_dir}", lsst_distrib_dir)
        if "custom_lsst_setup" in data_dict:  # pragma: no cover
            custom_lsst_setup = data_dict["custom_lsst_setup"]
            prepend += f"\n{custom_lsst_setup}"

        command = f"pipetask report --full-output-filename {report_url} {butler_repo} {graph_url}"
        write_bash_script(script_url, command, prepend=prepend)

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
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        fake_status = kwargs.get("fake_status", None)
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
        if parent.level != LevelEnum.job:  # pragma: no cover
            raise CMBadParameterTypeError(f"Script parent is a {parent.level}, not a LevelEnum.job")
        await session.refresh(parent, attribute_names=["tasks_"])
        for task_ in parent.tasks_:
            await TaskSet.delete_row(session, task_.id)
        return update_fields
