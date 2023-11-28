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
from lsst.ctrl.bps import BaseWmsService, WmsRunReport, WmsStates
from lsst.utils import doImport

from ..common.enums import StatusEnum, TaskStatusEnum, WmsMethodEnum
from .functions import load_wms_reports
from .script_handler import FunctionHandler, ScriptHandler

WMS_TO_JOB_STATUS_MAP = {
    WmsStates.UNKNOWN: None,
    WmsStates.MISFIT: None,
    WmsStates.UNREADY: StatusEnum.waiting,
    WmsStates.READY: StatusEnum.ready,
    WmsStates.PENDING: StatusEnum.prepared,
    WmsStates.RUNNING: StatusEnum.running,
    WmsStates.DELETED: StatusEnum.failed,
    WmsStates.HELD: StatusEnum.running,
    WmsStates.SUCCEEDED: StatusEnum.reviewable,
    WmsStates.FAILED: StatusEnum.failed,
    WmsStates.PRUNED: StatusEnum.failed,
}


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


def parse_bps_stdout(url: str) -> dict[str, str]:
    """Parse the std from a bps submit job"""
    out_dict = {}
    with open(url, encoding="utf8") as fin:
        line = fin.readline()
        while line:
            tokens = line.split(":")
            if len(tokens) != 2:  # pragma: no cover
                line = fin.readline()
                continue
            out_dict[tokens[0]] = tokens[1]
            line = fin.readline()
    return out_dict


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
        run_coll = resolved_cols["run"]
        input_colls = resolved_cols["inputs"]
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        script_url = await self._set_script_files(session, script, prod_area)
        butler_repo = data_dict["butler_repo"]
        lsst_version = data_dict["lsst_version"]

        script_url = await self._set_script_files(session, script, prod_area)
        json_url = os.path.abspath(os.path.expandvars(f"{prod_area}/{script.fullname}_log.json"))
        config_url = os.path.abspath(os.path.expandvars(f"{prod_area}/{script.fullname}_bps_config.yaml"))
        log_url = os.path.abspath(os.path.expandvars(f"{prod_area}/{script.fullname}.log"))

        bps_script_template = await specification.get_script_template(
            session,
            data_dict["bps_script_template"],
        )
        bps_yaml_template = await specification.get_script_template(
            session,
            data_dict["bps_yaml_template"],
        )

        command = f"bps --log-file {json_url} --no-log-tty submit {os.path.abspath(config_url)} > {log_url}"

        prepend = bps_script_template.data["text"].replace("{lsst_version}", lsst_version)
        await write_bash_script(script_url, command, prepend=prepend)

        workflow_config = bps_yaml_template.data.copy()

        async with session.begin_nested():
            await session.refresh(parent, attribute_names=["c_", "p_"])
            workflow_config["project"] = parent.p_.name
            workflow_config["campaign"] = parent.c_.name

        data_query = data_dict.get("data_query", None)
        workflow_config["submitPath"] = os.path.abspath(
            os.path.expandvars(f"{prod_area}/{parent.fullname}/submit"),
        )

        workflow_config["LSST_VERSION"] = os.path.expandvars(data_dict["lsst_version"])
        if "custom_lsst_setup" in data_dict:
            workflow_config["custom_lsst_setup"] = data_dict["lsst_custom_setup"]
        workflow_config["pipelineYaml"] = os.path.expandvars(data_dict["pipeline_yaml"])

        inCollection = ".".join(input_colls)

        payload = {
            "payloadName": parent.c_.name,
            "butlerConfig": butler_repo,
            "outputRun": run_coll,
            "inCollection": inCollection,
        }
        if data_query:
            payload["dataQuery"] = data_query

        workflow_config["payload"] = payload
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
    ) -> StatusEnum:
        slurm_status = await ScriptHandler._check_slurm_job(self, session, slurm_id, script, parent)
        if slurm_status == StatusEnum.accepted:
            await script.update_values(session, status=StatusEnum.accepted)
            bps_dict = parse_bps_stdout(script.log_url)
            panda_url = bps_dict["Run Id"]
            await parent.update_values(session, wms_job_id=panda_url)
        return slurm_status

    async def launch(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        if not isinstance(parent, Job):
            raise TypeError(f"Script {script} should not be run on {parent}")

        status = await ScriptHandler.launch(self, session, script, parent, **kwargs)

        if status == StatusEnum.running:
            await parent.update_values(session, stamp_url=script.stamp_url)
            await session.commit()
        return status


class BpsReportHandler(FunctionHandler):
    """Class to handle running BpsReport"""

    wms_svc_class_name: str | None = None

    def __init__(self, spec_block_id: int, **kwargs: dict) -> None:
        FunctionHandler.__init__(self, spec_block_id, **kwargs)
        self._wms_svc_class: types.ModuleType | type | None = None
        self._wms_svc: BaseWmsService | None = None

    def _get_wms_svc(self, **kwargs: Any) -> BaseWmsService:
        if self._wms_svc is None:
            if self.wms_svc_class_name is None:
                raise NotImplementedError(f"{type(self)} should not be used, use a sub-class instead")
            self._wms_svc_class = doImport(self.wms_svc_class_name)
            if isinstance(self._wms_svc_class, types.ModuleType):
                raise RuntimeError(f"Site class={self.wms_svc_class_name} is not a BaseWmsService subclass")
            self._wms_svc = self._wms_svc_class(kwargs)
        return self._wms_svc

    def _get_wms_report(
        self,
        wms_workflow_id: int,
    ) -> WmsRunReport:
        """Get the WmsRunReport for a job

        Paramters
        ---------
        wms_workflow_id : int | None
            WMS workflow id

        Returns
        -------
        report: WmsRunReport
            Report for requested job
        """
        wms_svc = self._get_wms_svc()
        return wms_svc.report(wms_workflow_id=wms_workflow_id)[0][0]

    async def _load_wms_reports(
        self,
        session: async_scoped_session,
        job: Job,
        wms_workflow_id: int | None,
    ) -> StatusEnum | None:
        """Load the job processing info

        Paramters
        ---------
        job: Job
            Job in question

        wms_workflow_id : int | None
            WMS workflow id

        Returns
        -------
        status: StatusEnum | None
            Status of requested job
        """
        if wms_workflow_id is None:
            return None
        wms_svc = self._get_wms_svc()
        wms_run_report = wms_svc.report(wms_workflow_id=wms_workflow_id)[0][0]
        status = WMS_TO_JOB_STATUS_MAP[wms_run_report.state]
        _job = await load_wms_reports(session, job.id, wms_run_report)
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
        if fake_status is not None:
            status = fake_status
        else:
            status = await self._load_wms_reports(session, parent, script.stamp_url)
        if status is None:
            status = script.status
        if status != script.status:
            await script.update_values(session, status=status)
            await session.commit()
        return status


class PandaScriptHandler(BpsScriptHandler):
    """Class to handle running Bps for panda jobs"""

    wms_method = WmsMethodEnum.panda


class PandaReportHandler(BpsReportHandler):
    """Class to handle running BpsReport for panda jobs"""

    wms_svc_class_name = "lsst.ctrl.bps.panda.PanDAService"


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
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        script_url = await self._set_script_files(session, script, prod_area)
        butler_repo = data_dict["butler_repo"]
        lsst_version = data_dict["lsst_version"]
        graph_url = os.path.expandvars(f"{prod_area}/{script.fullname}/submit/qg.out")
        report_url = os.path.expandvars(f"{prod_area}/{script.fullname}/submit/manifest_report.yaml")

        manifest_script_template = await specification.get_script_template(
            session,
            data_dict["manifest_script_template"],
        )
        prepend = manifest_script_template.data["text"].replace("{lsst_version}", lsst_version)

        command = f"pipetask report {butler_repo} {graph_url} {report_url}"
        await write_bash_script(script_url, command, prepend=prepend)

        return StatusEnum.prepared
