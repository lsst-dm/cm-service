"""Module implementing a State Machine for a Group."""

from __future__ import annotations

import shutil
from collections import ChainMap
from os.path import expandvars
from typing import Any

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
