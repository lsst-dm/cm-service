from collections.abc import Sequence
from itertools import chain
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from sqlalchemy.exc import NoResultFound
from sqlmodel import desc, or_, select
from transitions import EventData

from lsst.cmservice.core.common.enums import DEFAULT_NAMESPACE, ManifestKind, StatusEnum
from lsst.cmservice.core.common.errors import CMNoSuchManifestError
from lsst.cmservice.core.common.graph import (
    append_node_to_graph,
    delete_node_from_graph,
    insert_node_to_graph,
)
from lsst.cmservice.core.common.logging import LOGGER
from lsst.cmservice.core.common.splitter import Splitter, SplitterEnum, SplitterMapping
from lsst.cmservice.core.common.timestamp import element_time
from lsst.cmservice.core.db.campaigns_v2 import Edge, Manifest, Node
from lsst.cmservice.core.models.manifest import ButlerManifest, LibraryManifest, LsstManifest

from .meta import NodeMachine

logger = LOGGER.bind(module=__name__)


class StepMachine(NodeMachine):
    """Specific state model for a Node of kind GroupedStep.

    At each transition, the Machine will take some action to evolve the
    Campaign graph.

    - prepare
        - create new StepCollect Node in graph
        - determine number of groups and group membership
        - create new StepGroup Nodes in graph
    - start
        - create step collections in Butler
    - finish
        - (condition) campaign graph is valid
    - unprepare (rollback)
        - all dynamic nodes removed from the graph. Graph is reset to its state
          before prepare was triggered.

    Failure modes may include
        - Butler errors (can't query for group membership)
        - Bad inputs (group membership rules don't make sense)
        - WMS errors (can't schedule butler commands for collection management)
        - Invalid graph after trigger

    Attributes
    ----------
    anchor_group : Node
        As groups are created, the first one is cached as an "anchor group"
        for subsequent groups to parallelize with.
    """

    __kind__ = [ManifestKind.grouped_step]

    def __init__(
        self, *args: Any, o: Node, initial_state: StatusEnum = StatusEnum.waiting, **kwargs: Any
    ) -> None:
        super().__init__(*args, o=o, initial_state=initial_state, **kwargs)
        # TODO the self.db_model could be transitioned to a step-specific model
        self.anchor_group: UUID | None = None
        self.collect_group: UUID | None = None
        self.butler: ButlerManifest | None = None
        self.machine.before_prepare("do_prepare")
        self.machine.before_start("do_start")
        self.machine.before_unprepare("do_unprepare")
        self.machine.before_finish("do_finish")
        self.machine.before_reset("do_reset")
        self.machine.before_retry("do_retry")

    async def get_manifest[T: LibraryManifest](
        self, manifest_kind: ManifestKind, manifest_type: type[T]
    ) -> T:
        """Fetches the appropriate Manifest for the Campaign. The newest
        manifest of the specified Kind is retrieved from the campaign or
        the library namespace, and an object of `type[manifest_type]` is
        created and returned.

        Raises
        ------
        CMNoSuchManifestError
            Raised when the Node attempts to load a Manifest that cannot be
            found in the Campaign or the Library.
        """
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)
            assert self.session is not None

        # Look in the campaign namespace for the most recent Butler manifest,
        # falling back to the default namespace if one is not found.
        s = (
            select(Manifest)
            .where(Manifest.kind == manifest_kind)
            .where(
                or_(Manifest.namespace == self.db_model.namespace, Manifest.namespace == DEFAULT_NAMESPACE)
            )
            .order_by(desc(Manifest.version))
            .limit(1)
        )
        try:
            manifest = (await self.session.exec(s)).one()
            self.session.expunge(manifest)
        except NoResultFound:
            raise CMNoSuchManifestError(f"A required manifest was not found in the database: {manifest_kind}")

        o = manifest_type(**manifest.model_dump())
        o.metadata_.version = manifest.version
        return o

    async def get_predicates(self) -> tuple[str, ...]:
        """Determines the collection of data query predicates relevant to the
        group by joining the Campaign's predicates (as known from the Butler
        Library manifest) and the Step's predicates.
        """
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)
            assert self.butler is not None

        step_predicates: list[str] = self.db_model.configuration.get("predicates", [])
        return tuple(chain(self.butler.spec.predicates, step_predicates))

    async def get_splitter(self) -> Splitter:
        """Generates group-predicates according to the Node grouping rules."""
        if TYPE_CHECKING:
            assert self.butler is not None
            assert self.db_model is not None

        # select a splitter based on the Node's configuration
        splitter_config = self.db_model.configuration.get("groups", None)
        if splitter_config is None:
            return SplitterMapping["null"]()

        match SplitterEnum(splitter_config["split_by"]):
            case SplitterEnum.VALUES:
                splitter_type = SplitterMapping[SplitterEnum.VALUES.value]
            case SplitterEnum.QUERY:
                splitter_type = SplitterMapping[SplitterEnum.QUERY.value]
                splitter_config["butler_label"] = self.butler.spec.repo
                if self.butler.spec.collections.step_input is not None:
                    splitter_config["collections"] = [self.butler.spec.collections.step_input]
                else:
                    splitter_config["collections"] = [self.butler.spec.collections.campaign_input]

        return splitter_type(**splitter_config)

    async def make_group(self, with_predicates: Sequence[str]) -> None:
        """Creates a Step-Group Node in the campaign graph adjacent to self.

        Parameters
        ----------
        with_predicates : Sequence[str]
            An immutable sequence, e.g., a tuple, of string predicates to
            assign to this group's predicate attribute, all of which will be
            "AND"ed together to construct the group's data query.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None
            assert self.butler is not None

        logger.info("Creating step-group node", query=with_predicates)

        # The group ID can be effectively deterministic with a uuid in the
        # parent step's namespace using the group's predicates as its most
        # identifiable attribute.
        group_id = uuid5(self.db_model.id, hash(with_predicates).to_bytes(8, signed=True))

        # The group's name isn't very interesting or important, so we make sure
        # it's identifiably a group member of its parent step while including
        # a random component.
        group_nonce = group_id.hex[:8]
        group_name = f"{self.db_model.name}_group_{group_nonce}"

        # FIXME this might not be the first attempt at group-splitting, so do
        #       not assume version 1
        # TODO define "tries" for this transition.
        group_version = 1

        # TODO intial status for a group could be "paused" if campaign is set
        #      to auto-pause on group
        group_status = StatusEnum.waiting

        # The group configuration should be a fully-hydrated context for the
        # eventual rendering of the group's artifact templates.
        # TODO this will need to include the appropriate LSST stack manifest
        #      and any facility/site manifests
        group_butler = self.butler.spec.model_copy(
            update={
                "predicates": with_predicates,
                "collections": self.butler.spec.collections.model_copy(
                    update={
                        "step_input": (
                            f"{self.butler.spec.collections.campaign_public_output}/{self.db_model.name}/input"
                        ),
                        "step_output": (
                            f"{self.butler.spec.collections.campaign_public_output}/{self.db_model.name}_output"
                        ),
                        "step_public_output": (
                            f"{self.butler.spec.collections.campaign_public_output}/{self.db_model.name}"
                        ),
                        "group_output": (
                            f"{self.butler.spec.collections.campaign_public_output}/{self.db_model.name}/{group_nonce}"
                        ),
                        "run": (
                            f"{self.butler.spec.collections.campaign_public_output}/"
                            f"{self.db_model.name}/"
                            f"{group_nonce}/"
                            f"version_{group_version}"
                        ),
                    },
                ),
            },
        )
        # TODO model validate?
        group_configuration = {
            "butler": group_butler.model_dump(),
            "lsst": {},
            "facility": {},
            "wms": {},
        }
        group_metadata = {
            "crtime": element_time(),
            "manifests": {
                "butler": self.butler.metadata_.version,
                "lsst": 0,
                "facility": 0,
                "wms": 0,
            },
        }
        group = Node(
            id=group_id,
            name=group_name,
            namespace=self.db_model.namespace,
            version=group_version,
            kind=ManifestKind.group,
            status=group_status,
            metadata_=group_metadata,
            configuration=group_configuration,
        )

        # add new group to session
        self.session.add(group)
        # add new group to graph via append, in parallel with the anchor group
        # or via insert as the anchor group
        if self.anchor_group is not None:
            await append_node_to_graph(
                node_0=self.anchor_group,
                node_1=group_id,
                namespace=self.db_model.namespace,
                session=self.session,
                commit=False,
            )
        else:
            self.anchor_group = group_id
            await insert_node_to_graph(
                node_0=self.db_model.id,
                node_1=group_id,
                namespace=self.db_model.namespace,
                session=self.session,
                commit=False,
            )

    async def make_collect_step(self) -> None:
        """Creates a Collect-Groups Node in the campaign graph adjacent to
        each Step-Group.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None
            assert self.butler is not None

        collect_name = f"{self.db_model.name}_collect_groups"

        collect_butler = self.butler.spec.model_copy(
            update={
                "collections": self.butler.spec.collections.model_copy(
                    update={
                        "step_output": (
                            f"{self.butler.spec.collections.campaign_public_output}/{self.db_model.name}_output"
                        ),
                        "step_public_output": (
                            f"{self.butler.spec.collections.campaign_public_output}/{self.db_model.name}"
                        ),
                    },
                ),
            },
        )

        collect_configuration: dict[str, dict] = {
            "butler": collect_butler.model_dump(),
            "lsst": {},
            "facility": {},
            "wms": {},
        }

        collect = Node(
            name=collect_name,
            namespace=self.db_model.namespace,
            id=uuid5(self.db_model.id, f"{collect_name}.1"),
            version=1,
            kind=ManifestKind.collect_groups,
            status=StatusEnum.waiting,
            metadata_=dict(crtime=element_time()),
            configuration=collect_configuration,
        )
        self.session.add(collect)

        # add collect step to graph via insert
        await insert_node_to_graph(
            node_0=self.db_model.id,
            node_1=collect.id,
            namespace=self.db_model.namespace,
            session=self.session,
            commit=False,
        )
        self.collect_group = collect.id

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
        predicates: list[str]
        groups:
          split_by: Literal["values", "query"]
          field: str
          values: List[] (only if split_by == values)
          dataset: str (only if split_by == query)
          min_groups: int
          max_size: int
        ```
        """
        if TYPE_CHECKING:
            assert self.session is not None

        self.butler = await self.get_manifest(ManifestKind.butler, ButlerManifest)
        self.lsst = await self.get_manifest(ManifestKind.lsst, LsstManifest)
        predicates = await self.get_predicates()
        splitter = await self.get_splitter()

        await self.make_collect_step()

        async for predicate in splitter.split():
            await self.make_group(with_predicates=(predicates + (predicate,)))

        await self.session.commit()

    async def do_unprepare(self, event: EventData) -> None:
        """Unprepare removes step groups from the graph."""
        # If there is an anchor group known to the machine, remove each node
        # parallel to it.
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None

        if self.anchor_group is not None:
            anchor_node = await self.session.get_one(Node, ident=self.anchor_group, with_for_update=True)
            group_nodes_s = (
                select(Edge.target)
                .with_for_update()
                .where(Edge.source == self.db_model.id)
                .where(Edge.target != anchor_node.id)
            )
            group_nodes = (await self.session.exec(group_nodes_s)).all()

            # TODO: Nodes should not be deleted unless they have been edited.
            for group in group_nodes:
                await delete_node_from_graph(
                    node_0=group,
                    namespace=self.db_model.namespace,
                    session=self.session,
                    heal=False,
                    keep_node=False,
                )

            # Remove the anchor group itself
            await delete_node_from_graph(
                node_0=anchor_node.id,
                namespace=self.db_model.namespace,
                session=self.session,
                heal=True,
                keep_node=False,
            )

        # Remove the collect_groups_node
        if self.collect_group is not None:
            collect_group = await self.session.get_one(Node, ident=self.collect_group, with_for_update=True)

            await delete_node_from_graph(
                node_0=collect_group.id,
                namespace=self.db_model.namespace,
                session=self.session,
                heal=True,
                keep_node=False,
            )

        await self.session.commit()

        if self.activity_log_entry is not None:
            self.activity_log_entry.detail["message"] = (
                f"{self.db_model.name} was rolled back via '{event.event.name}'"
            )

    async def do_start(self, event: EventData) -> None:
        """Start should create butler collections for the step."""
        ...

    async def do_finish(self, event: EventData) -> None:
        """Finish should assert as a condition that the step's butler
        collections exist and that the campaign graph is valid.
        """
        ...

    async def do_reset(self, event: EventData) -> None:
        """Transition method between "failed" and "waiting"."""
        # trigger retry to transition to ready
        await self.trigger("retry")
        # trigger unprepare to transition to waiting
        await self.trigger("unprepare")

    async def do_retry(self, event: EventData) -> None:
        """Transition method between "failed" and "ready"."""
        ...


class GroupMachine(NodeMachine):
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


class StepCollectMachine(NodeMachine):
    """Specific state model for a Node of kind StepCollect.

    At each transition:

    - prepare
        - determine StepGroup Nodes immediately antecedent to Self
        - construct list of StepGroup "output" collections to chain together

    - start
        - create step output chained butler collection
        - (condition) ancestor output collections exist in butler?
        - add each ancestor output collection to step output chain

    - finish
        - (condition) all ancestor output collections in chain
    """

    __kind__ = [ManifestKind.collect_groups]

    ...
