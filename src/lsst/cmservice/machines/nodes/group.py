"""Module implementing a State Machine for a Group."""

import shutil
from typing import TYPE_CHECKING

from fastapi.concurrency import run_in_threadpool
from transitions import EventData

from ...common.enums import ManifestKind
from ...common.logging import LOGGER
from .meta import NodeMachine
from .mixin import ActionNodeMixin

logger = LOGGER.bind(module=__name__)


class GroupMachine(NodeMachine, ActionNodeMixin):
    """Specific state model for a Node of kind StepGroup.

    At each transition:

    - prepare
        - create artifact output directory
        - collect all relevant configuration Manifests
        - render bps workflow artifacts
        - create butler in collection(s)

    - start
        - bps submit
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
    """

    __kind__ = [ManifestKind.step_group]

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""
        self.machine.before_prepare("do_prepare")
        self.machine.before_unprepare("do_unprepare")

    async def do_prepare(self, event: EventData) -> None:
        """Action method invoked when executing the "prepare" transition."""
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None

        self.templates = [
            ("wms_submit_sh.j2", f"{self.db_model.name}.sh"),
            ("bps_submit_yaml.j2", f"{self.db_model.name}_bps_config.yaml"),
        ]

        # Create a group-specific working directory in the campaign's artifact
        # path.
        if artifact_location := await self.get_artifact_path(event):
            group_artifact_location = artifact_location / self.db_model.name
            await group_artifact_location.mkdir(parents=False, exist_ok=False)

        # Render output artifacts
        await self.render_action_templates(event)

    async def do_unprepare(self, event: EventData) -> None:
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None
        artifact_location = await self.get_artifact_path(event)

        # Remove any group-specific working directory from the campaign's
        # artifact path.
        if artifact_location and artifact_location.exists():
            group_artifact_location = artifact_location / self.db_model.name
            await run_in_threadpool(shutil.rmtree, group_artifact_location)

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
