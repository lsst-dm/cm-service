from collections.abc import Sequence
from itertools import chain
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from sqlalchemy.exc import NoResultFound
from sqlmodel import desc, or_, select
from transitions import EventData

from ...common.enums import DEFAULT_NAMESPACE, ManifestKind, StatusEnum
from ...common.errors import CMNoSuchManifestError
from ...common.graph import (
    NodeData,
    append_node_to_graph,
    delete_node_from_graph,
    find_endpoints_in_directed_graph,
    graph_from_edge_list_v2,
    insert_node_to_graph,
    subgraph_between_nodes,
)
from ...common.logging import LOGGER
from ...common.splitter import Splitter, SplitterEnum, SplitterMapping
from ...common.timestamp import element_time
from ...config import config
from ...db.campaigns_v2 import Edge, Manifest, Node
from ...models.manifest import (
    BpsManifest,
    ButlerManifest,
    FacilityManifest,
    LibraryManifest,
    LsstManifest,
    WmsManifest,
)
from .meta import NodeMachine
from .mixin import FilesystemActionMixin, HTCondorLaunchMixin

logger = LOGGER.bind(module=__name__)


class StepMachine(NodeMachine, FilesystemActionMixin, HTCondorLaunchMixin):
    """Specific state model for a Node of kind GroupedStep.

    At each transition, the Machine will take some action to evolve the
    Campaign graph.

    - prepare
        - create directory at artifact path
        - create new StepCollect Node in graph
        - determine number of groups and group membership
        - create new StepGroup Nodes in graph
    - start
        - create input collection for the step in Butler
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
    anchor_group : UUID
        As groups are created, the first one is cached as an "anchor group"
        for subsequent groups to parallelize with.

    collect_group : UUID
        A collect step is created as the exit node for a Step's sub-graph
        network of groups.
    """

    __kind__ = [ManifestKind.step]
    anchor_group: UUID | None
    collect_group: UUID | None

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""

        self.templates = [
            ("wms_submit_sh.j2", f"{self.db_model.name}.sh"),
        ]
        self.anchor_group: UUID | None = None
        self.collect_group: UUID | None = None
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

        # Look in the campaign namespace for the most recent manifest,
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
        logger.info("Creating step-group node", query=with_predicates)

        # The group ID can be effectively deterministic with a uuid in the
        # parent step's namespace using the group's predicates as its most
        # identifiable attribute.
        group_id = uuid5(self.db_model.id, hash(with_predicates).to_bytes(8, signed=True))

        # The group's name isn't very interesting or important, so we make sure
        # it's identifiably a group member of its parent step while including
        # a random component.
        # TODO Make the nonce a more ordinal or communicable name
        group_nonce = group_id.hex[:8]
        group_name = f"{self.db_model.name}_group_{group_nonce}"

        # FIXME this might not be the first attempt at group-splitting, so do
        #       not assume version 1
        # TODO define "tries" for this transition.
        group_version = 1

        # TODO intial status for a group could be "paused" if campaign is set
        #      to auto-pause on group
        group_status = StatusEnum.waiting

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
        # FIXME What are we trying to accomplish here?
        group_configuration = {
            "butler": group_butler.model_dump(exclude_none=True),
            "bps": self.bps.spec.model_dump(exclude_none=True) | self.db_model.configuration.get("bps", {}),
            "lsst": self.lsst.spec.model_dump(exclude_none=True)
            | self.db_model.configuration.get("lsst", {}),
            "site": self.site.spec.model_dump(exclude_none=True)
            | self.db_model.configuration.get("site", {}),
            "wms": self.wms.spec.model_dump(exclude_none=True) | self.db_model.configuration.get("wms", {}),
        }
        group_metadata = {
            "crtime": element_time(),
            "step": str(self.db_model.id),
            "artifact_path": str(self.artifact_path),
            "manifests": {
                "butler": self.butler.metadata_.version,
                "bps": self.bps.metadata_.version,
                "lsst": self.lsst.metadata_.version,
                "site": self.site.metadata_.version,
                "wms": self.wms.metadata_.version,
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
        collect_metadata = {
            "crtime": element_time(),
            "step": str(self.db_model.id),
            "artifact_path": str(self.artifact_path),
        }
        collect = Node(
            name=collect_name,
            namespace=self.db_model.namespace,
            id=uuid5(self.db_model.id, f"{collect_name}.1"),
            version=1,
            kind=ManifestKind.collect_groups,
            status=StatusEnum.waiting,
            metadata_=collect_metadata,
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

    async def butler_prepare(self, event: EventData) -> None:
        """Prepares a Butler operation for the step to execute during its
        running phase.

        A Step constructs an "input collection" that each of its groups will
        use in their BPS Workflow. This collection is a chained collection of
        all previous Step outputs together with the Campaign input collect-
        ion(s).

        The runtime configuration chain for the Node is updated with a dynamic
        Butler manifest.
        """

        # A subgraph view of the Campaign from the Start to the Current Step
        # provides the set of Step Output collections we need to include in our
        # Step Input collection.
        s = select(Edge).where(Edge.namespace == self.db_model.namespace)
        edges = (await self.session.exec(s)).all()
        graph = await graph_from_edge_list_v2(edges, self.session)
        source, _ = find_endpoints_in_directed_graph(graph)
        step_subgraph = subgraph_between_nodes(graph, source, self.db_model.id)

        # find all output collections for "collect" steps in the subgraph and
        # add them to the set of intermediate collections to be used in the
        # step_input collection used by each group.
        intermediate_collections = []
        data: NodeData
        for _, data in step_subgraph.nodes.data():
            if data["model"].kind is ManifestKind.collect_groups:
                step_config = data["model"].configuration
                step_output = step_config.get("butler", {}).get("collections", {}).get("step_output")
                if step_output is None:
                    raise RuntimeError("Predecessor collect step has no output collection")
                intermediate_collections.append(step_output)

        self.command_templates = [
            (
                "{{butler.exe_bin}} collection-chain {{butler.repo}} {{butler.collections.step_input}}"
                "{% for collection in butler.collections.intermediates %} {{collection}}{% endfor %}"
                "{% for collection in butler.collections.campaign_input %} {{collection}}{% endfor %}"
            )
        ]
        # Prepare a Butler runtime config to add to the Node's config chain,
        # which includes additional collection information beyond what's spec-
        # ified in the Node's reference Butler manifest.
        butler_config: dict[str, Any] = {}
        butler_config["exe_bin"] = config.butler.butler_bin
        butler_config["collections"] = self.butler.spec.collections.model_copy(
            update={
                "intermediates": intermediate_collections,
                "step_input": (
                    f"{self.butler.spec.collections.campaign_public_output}/{self.db_model.name}/input"
                ),
            }
        )

        self.configuration_chain["butler"] = self.configuration_chain["butler"].new_child(butler_config)

    async def do_prepare(self, event: EventData) -> None:
        """Prepare should create new nodes for each of the step groups.

        Definition of group loadout is determined by a "groups" key in the
        node's configuration. If the "groups" key is ``null`` then no group-
        splitting occurs, but the Node still spawns a single nominal group.

        The result of group splitting is the generation of new predicates to
        include in the Node's "base_query".

        The full specification of a Node's grouping configuration is defined
        in the ``step_config.jsonschema`` file. A simplified version
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

        # Assemble the core configuration manifests from the campaign or
        # library namespaces, which will be "baked into" the group's
        # configuration.
        # FIXME this ignores that there could be multiple manifests of a single
        # kind in a campaign that differ by name -- example, multiple Site
        # manifests for different facilities, or multiple Wms manifests for
        # different batch systems.
        self.butler = await self.get_manifest(ManifestKind.butler, ButlerManifest)
        self.lsst = await self.get_manifest(ManifestKind.lsst, LsstManifest)
        self.bps = await self.get_manifest(ManifestKind.bps, BpsManifest)
        self.wms = await self.get_manifest(ManifestKind.wms, WmsManifest)
        self.site = await self.get_manifest(ManifestKind.site, FacilityManifest)

        predicates = await self.get_predicates()
        splitter = await self.get_splitter()

        # Call Prepare methods associated with mixins
        # TODO this should follow an event-dispatch or observer pattern
        await self.action_prepare(event)
        await self.butler_prepare(event)
        await self.launch_prepare(event)

        await self.make_collect_step()

        async for predicate in splitter.split():
            await self.make_group(with_predicates=(predicates + (predicate,)))

        await self.session.commit()

        # TODO separate before/after trigger events
        await self.render_action_templates(event)

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


class StepCollectMachine(NodeMachine, FilesystemActionMixin, HTCondorLaunchMixin):
    """Specific state model for a Node of kind StepCollect.

    At each transition:

    - prepare
        - determine Group Nodes immediately antecedent to Self
        - construct list of Group "output" collections to chain together

    - start
        - create step output chained butler collection
        - (condition) ancestor output collections exist in butler?
        - add each ancestor output collection to step output chain

    - finish
        - (condition) all ancestor output collections in chain

    Attributes
    ----------
    collections : list[str]
        A list of Butler collection names. Specifically, this is the set of
        all predeccesor output collections generated in the Step's
        subnetwork of group Nodes. This attribute is populated by the "prepare"
        trigger.
    """

    __kind__ = [ManifestKind.collect_groups]
    collections: list[str]

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""
        if TYPE_CHECKING:
            assert self.db_model is not None

        self.templates = [
            ("wms_submit_sh.j2", f"{self.db_model.name}.sh"),
        ]
        self.machine.before_prepare("do_prepare")
        self.machine.before_unprepare("do_unprepare")

    async def do_prepare(self, event: EventData) -> None:
        """Determine the set of group output collections to chain together for
        the step's output collection.

        One way to do this is to look at the Group nodes who are immediate
        predeccesors to this node in the graph (e.g., by looking at the Edges
        table). This approach may be naive because other Nodes could be
        arbitrarily inserted into the graph between the group and collect nodes
        such as a breakpoint. In this case, the Breakpoint node would cause
        the simple look-back query to have missing information.

        The role of the collect step in a graph is to be the definite exit node
        from a step's sub network of steps. This means that for any given
        collect node, there will be one and only one step node in its reverse
        path, so if we walk the graph backward from this node along any edge,
        we will reach the same step node along any of those paths, and each of
        those paths will have exactly one group node, irrespective of any other
        nodes along that path, e.g., breakpoints.

        This should also mean that for any subnetwork defined between step and
        collect, the set of groups within that network is complete.

        This points to the idea that on creation, the originating step node
        for which this collect step is created should be cached as a metadata.
        """

        # construct a graph where the source is the originating step and the
        # sink is the current collect node. This represents a subgraph of the
        # entire campaign that contains the network of this step and its groups
        parent_step = self.db_model.metadata_.get("step")
        if parent_step is None:
            raise RuntimeError("Collect node has no ancestor step node")
        s = select(Edge).where(Edge.namespace == self.db_model.namespace)
        edges = (await self.session.exec(s)).all()
        graph = await graph_from_edge_list_v2(edges, self.session)
        subgraph = subgraph_between_nodes(graph, UUID(parent_step), self.db_model.id)

        # For every node in the subgraph of kind group, fish out its output
        # collection.
        groups = [
            node[1]["model"] for node in subgraph.nodes.data() if node[1]["model"].kind is ManifestKind.group
        ]
        self.collections = [group.configuration["butler"]["collections"]["group_output"] for group in groups]

        # perform specific preparations
        await self.action_prepare(event)
        await self.launch_prepare(event)
        await self.butler_prepare(event)

        # Render executable artifacts
        await self.render_action_templates(event)

    async def butler_prepare(self, event: EventData) -> None:
        """Sets the command template and runtime configuration in preparation
        for Butler operations.
        """
        self.command_templates = [
            (
                "{{butler.exe_bin}} collection-chain {{butler.repo}} {{butler.collections.step_output}}"
                "{% for collection in butler.input_collections %} {{collection}}{% endfor %} "
            ),
            (
                "{{butler.exe_bin}} collection-chain {{butler.repo}} "
                "{{butler.collections.step_public_output}} {{butler.collections.step_output}} "
                "{% for collection in butler.collections.campaign_input %} {{collection}}{% endfor %} "
            ),
        ]
        # Prepare a Butler runtime config to add to the Node's config chain
        butler_config: dict[str, Any] = {}
        butler_config["exe_bin"] = config.butler.butler_bin
        # FIXME this should follow the same grammar as other butler runtime
        # configs used in other nodes, but it doesn't really matter as long
        # as the variable is found at render time.
        butler_config["input_collections"] = self.collections

        self.configuration_chain["butler"] = self.configuration_chain["butler"].new_child(butler_config)

    async def do_unprepare(self, event: EventData) -> None: ...
