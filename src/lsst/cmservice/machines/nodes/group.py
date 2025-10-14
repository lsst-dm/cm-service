"""Module implementing a State Machine for a Group."""

from __future__ import annotations

import shutil
from collections import ChainMap
from os.path import expandvars
from types import ModuleType
from typing import Any

from anyio import Path
from fastapi.concurrency import run_in_threadpool
from transitions import EventData

from lsst.ctrl.bps import WmsRunReport, WmsStates
from lsst.utils import doImport

from ...common.bash import parse_bps_stdout
from ...common.enums import ManifestKind, StatusEnum
from ...common.flags import Features
from ...common.logging import LOGGER
from ...config import config
from ...handlers.functions import status_from_bps_report
from ..lib import materialize_activity_log
from .meta import NodeMachine
from .mixin import FilesystemActionMixin, HTCondorLaunchMixin

logger = LOGGER.bind(module=__name__)


class GroupMachine(NodeMachine, FilesystemActionMixin, HTCondorLaunchMixin):
    """Specific state model for a Node of kind Group.

    At each transition:

    - prepare
        - create artifact output directory
        - collect all relevant configuration Manifests
        - render bps workflow artifacts

    - start
        - bps submit (htcondor submit)
        - (after_start) determine bps submit directory

    - finish
        - (condition) bps report == done
        - create butler out collection(s)

    - fail
        - read/parse bps output logs

    - stop (rollback)
        - bps cancel

    - unprepare (rollback)
        - remove artifact output directory
        - Butler collections are not modified (paint-over pattern)

    Failure modes may include:
        - Unwritable artifact output directory
        - Manifests insufficient to render bps workflow artifacts
        - Butler errors
        - BPS or other middleware errors

    Attributes
    ----------
    configuration_chain
        A mapping of manifest names to ChainMap instances providing hierarchal
        lookup for configuration elements, including the node's explicit
        configuration, campaign-level configuration, and runtime configuration.

    artifact_path
        A path object referring to the group's working directory, to which
        templates are rendered.
    """

    __kind__ = [ManifestKind.group]
    configuration_chain: dict[str, ChainMap]
    artifact_path: Path

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""

        self.machine.before_prepare("do_prepare")
        self.machine.before_unprepare("do_unprepare")
        self.machine.before_start("do_start")

        self.templates = [
            ("bps_submit_yaml.j2", f"{self.db_model.name}_bps_config.yaml"),
            ("wms_submit_sh.j2", f"{self.db_model.name}.sh"),
        ]

    async def render_bps_includes(self, event: EventData) -> list[str]:
        """BPS Include files get special treatment here for legacy and pract-
        ical reasons. Any file indicated as an "include" may refer to a file
        with an absolute path, a path with environment variables, and/or a
        path with BPS variables:

        ```
        - /absolute/path/to/file.yaml
        - ${ENV_VAR}/path/to/file.yaml
        - ${ENV_VAR}path/to/{special_file_name}
        ```

        At the time of submitting the BPS Workflow, all the include paths must
        refer to locations meaningful and reachable from the BPS executive env-
        ironment.

        It is not likely but possible for an include file to be known to CM but
        not the executive environment; slightly more likely that an environment
        variable be set for CM but not for the executive environment; but the
        most likely case is that a path is intelligible only to the executive
        environment because of stack-populated environment variables and/or BPS
        variables set by *other include files*.

        This function is not concerned with understanding the correct *order*
        of include files, or what *role* the included file serves in the BPS
        config, but whatever list of include files it renders are kept in the
        original order and handled such that:

        - Any environment variables that CM can resolve are resolved;
        - Any filesystem paths that CM can make absolute are made absolute;
        - Everything else is left for BPS to resolve.

        Additionally, this function combines include directives from multiple
        manifests into a single collection. Deduplication occurs after the
        resolution steps above, and order is preserved within manifests.
        """
        # This set is used for deduplication only
        includes_set: set[str] = set()

        # Order is preserved in this list
        bps_includes: list[str] = []

        # Assemble a omnibus set of includes from multiple
        include_candidates: list[str] = [
            *self.configuration_chain["bps"].get("include_files", []),
            *self.configuration_chain["butler"].get("include_files", []),
            *self.configuration_chain["wms"].get("include_files", []),
        ]

        for include in include_candidates:
            to_include: str | Path = expandvars(include)
            # If the potential include file has an unexpanded env var, we
            # delegate that expansion to the bps runtime, since it may
            # refer to a stack env var we do not understand.
            if "$" in str(to_include):
                if str(to_include) in includes_set:
                    pass
                else:
                    includes_set.add(str(to_include))
                    bps_includes.append(str(to_include))
                continue

            # Resolve any paths known to CM
            try:
                to_include = await Path(to_include).resolve(strict=True)
            except FileNotFoundError:
                # The path is not known to CM. This exception is raised because
                # strict=True, and we don't want half-resolved paths passing
                # into the BPS file, so if CM can't resolve the entire path
                # then we defer it to BPS.
                pass

            if str(to_include) in includes_set:
                pass
            else:
                includes_set.add(str(to_include))
                bps_includes.append(str(to_include))

        return bps_includes

    async def bps_prepare(self, event: EventData) -> None:
        """Prepares a configuration chain link for a BPS command."""

        if not hasattr(self, "templates") or self.templates is None:
            raise RuntimeError("No BPS submit template known to Node.")

        bps_submit_path: Path | None
        for template, filename in self.templates:
            if template == "bps_submit_yaml.j2":
                bps_submit_path = await (self.artifact_path / filename).resolve()

        if bps_submit_path is None:
            raise RuntimeError("No BPS submit template known to Node.")

        self.command_templates = [
            (
                "{{bps.exe_bin}} --log-file {{bps.exe_log}} "
                "--no-log-tty submit {{bps.submit_yaml}} > {{bps.stdout_log}}"
            )
        ]

        # Prepare a BPS runtime configuration to add to the Node's config chain
        bps_config: dict[str, Any] = {}
        bps_config["exe_bin"] = "true" if Features.MOCK_BPS in config.features.enabled else config.bps.bps_bin
        bps_config["exe_log"] = bps_submit_path.with_name(f"{self.db_model.name}_log.json")
        bps_config["submit_yaml"] = bps_submit_path
        bps_config["stdout_log"] = bps_submit_path.with_name(f"{self.db_model.name}.log")

        # Prepare a BPS payload
        bps_payload: dict[str, Any] = {}
        bps_payload["payloadName"] = self.db_model.name
        bps_payload["butlerConfig"] = self.configuration_chain["butler"]["repo"]
        bps_payload["output"] = self.configuration_chain["butler"]["collections"]["group_output"]
        bps_payload["outputRun"] = self.configuration_chain["butler"]["collections"]["run"]
        bps_payload["inCollection"] = self.configuration_chain["butler"]["collections"]["step_input"]
        bps_payload["dataQuery"] = " AND ".join(self.configuration_chain["butler"]["predicates"])

        bps_config["payload"] = bps_payload

        # Prepare BPS Include Files
        bps_config["include_files"] = await self.render_bps_includes(event)
        self.configuration_chain["bps"] = self.configuration_chain["bps"].new_child(bps_config)

    async def do_prepare(self, event: EventData) -> None:
        """Action method invoked when executing the "prepare" transition."""

        # A Mixin should implement a action_prepare
        await self.action_prepare(event)

        await self.bps_prepare(event)

        # A Mixin should implement a launch_prepare
        await self.launch_prepare(event)

        # Render output artifacts
        await self.render_action_templates(event)

    async def do_unprepare(self, event: EventData) -> None:
        """Action method invoked when executing the "unprepare" transition."""
        logger.info("Unpreparing Node", id=str(self.db_model.id))
        await self.get_artifact_path(event)

        # Remove any group-specific working directory from the campaign's
        # artifact path.
        if await self.artifact_path.exists():
            await run_in_threadpool(shutil.rmtree, self.artifact_path)

    async def check_start(self, event: EventData) -> None:
        """Callback invoked after the machine has entered the Start state but
        before the transition is finalized.
        """
        # The timing on this is flexible. We don't expect to have bps output
        # immediately after transitioning to a running state via "start", but
        # this callback is also invoked by the "is_done_running" conditional
        # callback.
        await self.capture_bps_stdout(event)

    async def is_done_running(self, event: EventData) -> bool:
        """Checks whether the WMS job is finished or not based on the result of
        a bps-report or similar. Returns a True value if the batch is done and
        good, a False value if it is still running. Raises an exception in any
        other terminal WMS state (HELD or FAILED).
        """
        # TODO implementation of is_done_running for a group (or really any
        # node whose "launched" script is not its product, e.g., a bps-runner)
        # differs from a meta/step node because it's not the launcher result
        # we're interested in. Instead, the launcher result (i.e., did we
        # as far as we know successfully execute the script that calls bps?)
        # is a condition of successfully *entering* the running state, not
        # *exiting* it.

        # Phase 1: super() is_done_running for launcher status
        launch_status = await super().is_done_running(event)
        logger.debug("HTCondor Launch Status determined", id=str(self.db_model.id), outcome=launch_status)
        if not launch_status:
            return launch_status

        # Phase 2: make sure our launch transition has resulted in BPS output
        logger.debug("Checking for BPS Output", id=str(self.db_model.id))
        await self.check_start(event)
        if self.db_model.metadata_["bps"].get("Submit dir") is None:
            logger.debug("No BPS Output Discovered for Node", id=str(self.db_model.id))
            return False

        # Phase 3: BPS Report status for payload status
        # Phase 3 can itself be split into 2 sub-phases:
        # Phase 3A: Quick BPS Status
        # Phase 3B: Full BPS Report
        return await self.check_bps_report(event)

    async def capture_bps_stdout(self, event: EventData) -> None:
        """Read the BPS stdout log file indicated by the node's configuration.

        The BPS StdOut log should include the SubmitDir (used for subsequent
        BPS commands as an "id") and a WMS job ID (different to the job id
        determined by the launcher, i.e., this should be the job id of the
        actual payload).
        """
        # We must have a reference to a BPS stdout log in the first place
        if (bps_stdout_log := self.configuration_chain["bps"].get("stdout_log")) is None:
            raise RuntimeError("No BPS Stdout Log set in Config Chain")

        logger.debug("Checking BPS stdout Log", id=str(self.db_model.id), artifact=str(bps_stdout_log))

        # Call a method provided by the ActionMixin to COPY the requested file
        # to a temporary location.
        bps_dict: dict[str, str] = {}
        async for bps_stdout in self.get_artifact(event, bps_stdout_log):
            # parse the bps stdout file
            bps_dict = await parse_bps_stdout(bps_stdout)

        if not len(bps_dict):
            logger.warning(
                "Did not receive a BPS stdout log from ActionMixin",
                id=self.db_model.id,
                artifact=bps_stdout_log,
            )
        else:
            logger.debug(
                "Discovered BPS Submit Directory", id=str(self.db_model.id), artifact=bps_dict["Submit dir"]
            )
        # Attach the bps detail dictionary to the machine's node metadata
        new_metadata = self.db_model.metadata_.copy()
        new_metadata["bps"] = bps_dict
        self.db_model.metadata_ = new_metadata

        # Create an Activity Log entry
        activity_log_entry = self.get_activity_log(event)
        await materialize_activity_log(
            self.session,
            activity_log_entry,
            "bps_stdout",
            detail=bps_dict,
        )

    async def check_bps_report(self, event: EventData) -> bool:
        """Callback invoked during the transition from running to accepted. The
        machine's conditions will be invoked first (e.g., ``is_done_running``)
        and this method is called before the destination state is changed.

        Uses a previously discovered bps submit directory as an "id" to run
        BPS report.
        """
        if (bps_submit_dir := self.db_model.metadata_.get("bps", {}).get("Submit dir")) is None:
            raise RuntimeError("No BPS Submit dir known to machine")

        # Ensure we use the correct classes for the WMS Batch System
        if (wms_svc_class_name := self.configuration_chain["wms"].get("service_class")) is None:
            raise RuntimeError("No WMS Service Class known to machine")

        if isinstance(wms_svc_class := doImport(wms_svc_class_name), ModuleType):
            raise RuntimeError("WMS Service Class is a Module, not a BaseWmsService subclass")

        wms_svc_class_config: dict[str, str] = self.configuration_chain["wms"].get("service_class_config", {})

        wms_svc = wms_svc_class(config=wms_svc_class_config)

        # BPS Status
        # Using the bps_submit_dir as a WMS Workflow ID, it must be a existing
        # directory in order for BPS to identify it properly. Specifically, the
        # status is read from a `*.dag.dagman.log` file in the submit directory
        # - This only works with a shared filesystem between CM and BPS/WMS
        # FIXME use async run_thread
        bps_status: WmsStates
        status_message: str
        bps_status, status_message = wms_svc.get_status(bps_submit_dir)

        # TODO implement an OVERDUE check in here. This should be a simple
        # algorithm to identify long-running jobs (especially those that remain
        # idle because of no resource allocation)

        if len(status_message):
            logger.warning(status_message, id=str(self.db_model.id))

        # Create an Activity Log entry
        activity_log_entry = self.get_activity_log(event)
        activity_log_entry.detail = {"bps_status": bps_status.name, "bps_status_message": status_message}
        await materialize_activity_log(
            self.session,
            activity_log_entry,
            f"bps_status_{bps_status.name}",
        )

        match bps_status:
            case WmsStates.RUNNING:
                return False
            case WmsStates.FAILED:
                # TODO we want bps report if we are failed
                msg = "WMS Job is Failed"
                raise RuntimeError(msg)
            case WmsStates.DELETED:
                msg = "WMS Job is Deleted"
                raise RuntimeError(msg)
            case _:
                pass

        # BPS Report
        run_reports: list[WmsRunReport]
        report_message: str
        run_reports, report_message = wms_svc.report(bps_submit_dir)

        if len(report_message):
            logger.warning(report_message, id=str(self.db_model.id))

        wms_run_report = run_reports[0]
        # TODO load bps report result into database. Legacy CM uses the
        # wms_task_report table but this needs to be updated to v2
        status = status_from_bps_report(wms_run_report)

        # Create an Activity Log entry
        activity_log_entry = self.get_activity_log(event)
        activity_log_entry.detail = {"report_status": status.name, "report_message": report_message}
        await materialize_activity_log(
            self.session,
            activity_log_entry,
            "bps_report",
        )

        match status:
            case StatusEnum.accepted:
                return True
            case StatusEnum.blocked:
                # TODO need to disambiguate the type of failure here with a
                # specific exception
                msg = "WMS Job is Blocked"
                raise RuntimeError(msg)
            case StatusEnum.failed:
                msg = "WMS Job is Failed"
                raise RuntimeError(msg)
            case StatusEnum.running:
                return False
            case StatusEnum.reviewable:
                msg = "WMS Job is Indeterminate"
                # TODO this is a terminal state, so we could return True, or
                # raise a special exception to trigger a transition
                return True
            case _:
                return False

    async def do_retry(self, event: EventData) -> None:
        """Reverts the running status of a Group node to Ready.

        Basic options for retry are (1) retry from scratch (new bps submit) or
        retry with recovery (bps restart). Additional options based on emergent
        failure scenarios can be modeled here as well.
        """
        # TODO a group under retry (transition from failed->ready) may manip-
        # ulate the artifacts for the Node by changing, e.g., bps submit to
        # bps restart if a quantum graph file is present.

        # Potentially, a pilot could place a YAML file in the group's directory
        # with some flags related to how to retry the group
        ...
