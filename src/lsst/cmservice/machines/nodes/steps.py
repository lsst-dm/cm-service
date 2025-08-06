from typing import Any

from transitions import EventData

from ...common.enums import ManifestKind, StatusEnum
from ...db.campaigns_v2 import Node
from .meta import NodeMachine


class StepMachine(NodeMachine):
    """Specific state model for a Node of kind GroupedStep.

    The Step-Nodes may be the most involved state models, as the logic that
    must execute during each transition is complex. The behaviors are generally
    the same as the "scripts" associated with a Step/Group/Job in the legacy
    CM implementation.

    A summary of the logic at each transition:

    - prepare
        - determine number of groups and group membership
        - create new Manifest for each Group
    - start
        - create new StepGroup Nodes (reading prepared Manifests)
        - create new StepCollect Node
        - create edges
    - finish
        - (condition) campaign graph is valid
    - unprepare (rollback)
        - no action taken, but know that on the next use of "prepare"
          new versions of the group manifests may be created.

    Failure modes may include
        - Butler errors (can't query for group membership)
        - Bad inputs (group membership rules don't make sense)
    """

    __kind__ = [ManifestKind.grouped_step]

    def __init__(
        self, *args: Any, o: Node, initial_state: StatusEnum = StatusEnum.waiting, **kwargs: Any
    ) -> None:
        super().__init__(*args, o, initial_state, **kwargs)
        self.machine.before_prepare("do_prepare")
        self.machine.before_start("do_start")
        self.machine.before_unprepare("do_unprepare")
        self.machine.before_finish("do_finish")

    async def do_prepare(self, event: EventData) -> None: ...

    async def do_unprepare(self, event: EventData) -> None: ...

    async def do_start(self, event: EventData) -> None: ...

    async def do_finish(self, event: EventData) -> None: ...

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


class GroupMachine(NodeMachine):
    """Specific state model for a Node of kind StepGroup.

    A summary of the logic at each transition:

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

    ...


class StepCollectMachine(NodeMachine):
    """Specific state model for a Node of kind StepCollect.

    - prepare
        - create step output chained butler collection

    - start
        - (condition) ancestor output collections exist in butler?
        - add each ancestor output collection to step output chain

    - finish
        - (condition) all ancestor output collections in chain
    """

    __kind__ = [ManifestKind.collect_groups]

    ...
