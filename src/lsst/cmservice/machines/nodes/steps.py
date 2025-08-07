from typing import TYPE_CHECKING, Any

from transitions import EventData

from ...common.enums import ManifestKind, StatusEnum
from ...common.logging import LOGGER
from ...common.splitter import Splitter, SplitterEnum, SplitterMapping
from ...db.campaigns_v2 import Node
from .meta import NodeMachine

logger = LOGGER.bind(module=__name__)


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

    async def get_base_query(self) -> str:
        """Determines the base Butler query to which group predicates are
        appended. This query is any `base_query` configured in the Campaign's
        Butler manifest ANDed with any `base_query` configured in the Node's
        configuration.
        """
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)

        node_query = self.db_model.configuration.get("base_query")
        campaign_query = "1"
        return f"{campaign_query} AND {node_query}"

    async def get_splitter(self) -> Splitter:
        """Generates group-predicates according to the Node grouping rules."""
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)

        # select a splitter based on the Node's configuration
        group_config = self.db_model.configuration.get("groups", None)
        if group_config is None:
            return SplitterMapping["null"]()

        match SplitterEnum[group_config["split_by"]]:
            case SplitterEnum.VALUES:
                splitter_type = SplitterMapping[SplitterEnum.VALUES.value]
            case SplitterEnum.QUERY:
                splitter_type = SplitterMapping[SplitterEnum.QUERY.value]

        return splitter_type(**group_config)

    async def make_group(self, with_query: str) -> None:
        """Creates a Step-Group Node in the campaign graph adjacent to self."""
        logger.info("Creating step-group node", query=with_query)

    async def make_collect_step(self) -> None:
        """Creates a Collect-Groups Node in the campaign graph adjacent to
        each Step-Group.
        """
        ...

    async def do_prepare(self, event: EventData) -> None:
        """Prepare should create new nodes for each of the step groups.

        Definition of group loadout is determined by a "groups" key in the
        node's configuration. If the "groups" key is ``null`` then no group-
        splitting occurs, but the Node still spawns a single nominal group.

        The result of group splitting is the generation of new predicates to
        include in the Node's "base_query".

        The full specification of a Node's grouping configuration is defined
        in the ``grouped_step_config.jsonschema`` file. A simplified version
        follows.

        ```
        base_query: str
        groups:
          split_by: Literal["values", "query"]
          field: str
          values: List[] (only if split_by == values)
          dataset: str (only if split_by == query)
          min_groups: int
          max_size: int
        ```
        """
        base_query = await self.get_base_query()
        splitter = await self.get_splitter()
        async for predicate in await splitter.split():
            await self.make_group(with_query=f"{base_query} AND {predicate}")
        await self.make_collect_step()

    async def do_unprepare(self, event: EventData) -> None:
        """Unprepare should remove step groups from the graph, but only if they
        are still ``waiting`` and have not been manually edited; in this state
        a node is disposable.
        """
        ...

    async def do_start(self, event: EventData) -> None:
        """Start should create butler collections for the step."""
        ...

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
