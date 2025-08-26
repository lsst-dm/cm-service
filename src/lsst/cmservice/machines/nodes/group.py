"""Module implementing a State Machine for a Group."""

import shutil
from collections import ChainMap
from typing import TYPE_CHECKING, Any

from anyio import Path
from fastapi.concurrency import run_in_threadpool
from transitions import EventData

from ...common.enums import ManifestKind
from ...common.logging import LOGGER
from ...config import config
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
        self.templates = [
            ("bps_submit_yaml.j2", f"{self.db_model.name}_bps_config.yaml"),
            ("wms_submit_sh.j2", f"{self.db_model.name}.sh"),
        ]

    async def bps_prepare(self, event: EventData) -> None:
        """Prepares a configuration chain link for a BPS command."""

        self.command_templates = [
            (
                "{{bps.exe_bin}} --log-file {{bps.exe_log}} "
                "--no-log-tty submit {{bps.submit_yaml}} > {{bps.stdout_log}}"
            )
        ]

        bps_submit_path: Path | None
        for template, filename in self.templates:
            if template == "bps_submit_yaml.j2":
                bps_submit_path = await (self.artifact_path / filename).resolve()

        if bps_submit_path is None:
            raise RuntimeError("No BPS submit template known to Node.")

        # Prepare a BPS runtime configuration to add to the Node's config chain
        bps_config: dict[str, Any] = {}
        bps_config["exe_bin"] = config.bps.bps_bin
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
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None

        await self.get_artifact_path(event)

        # Remove any group-specific working directory from the campaign's
        # artifact path.
        if await self.artifact_path.exists():
            await run_in_threadpool(shutil.rmtree, self.artifact_path)

    async def is_successful(self, event: EventData) -> bool:
        """Checks whether the WMS job is finished or not based on the result of
        a bps-report or similar. Returns a True value if the batch is done and
        good, a False value if it is still running. Raises an exception in any
        other terminal WMS state (HELD or FAILED).

        ```
        bps_report: WmsStatusReport = get_wms_status_from_bps(...)

        match bps_report:
           case WmsStatusReport(wms_status="FINISHED"):
                return True
           case WmsStatusReport(wms_status="HELD"):
                raise WmsBlockedError()
           case WmsStatusReport(wms_status="FAILED"):
                raise WmsFailedError()
           case WmsStatusReport(wms_status="RUNNING"):
                return False
        ```
        """
        return True
