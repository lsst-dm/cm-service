from collections.abc import Iterable, Mapping, MutableSet, Sequence
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4, uuid5

import networkx as nx
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..common.enums import ManifestKind
from ..common.timestamp import element_time
from ..db import Script, ScriptDependency, Step, StepDependency
from ..db.campaigns_v2 import Edge, Node
from ..parsing.string import parse_element_fullname
from .types import AnyAsyncSession

type AnyGraphEdge = StepDependency | ScriptDependency
type AnyGraphNode = Step | Script


class InvalidCampaignGraphError(Exception): ...


async def graph_from_edge_list(
    edges: Sequence[AnyGraphEdge],
    node_type: type[AnyGraphNode],
    session: AnyAsyncSession,
) -> nx.DiGraph:
    """Given a sequence of edge-tuples, create a directed graph for these
    edges with nodes derived from database lookups of the related objects.
    """
    g = nx.DiGraph()
    g.add_edges_from([(e.prereq_id, e.depend_id) for e in edges])

    # Expect to refer to the appropriate node_type given an id to hydrate a
    # node from the database using the provided session.
    for node in g.nodes:
        db_node = await node_type.get_row(session, row_id=node)
        node_name = parse_element_fullname(db_node.fullname)
        g.nodes[node]["step"] = node_name.step
        g.nodes[node]["group"] = node_name.group
        g.nodes[node]["job"] = node_name.job
        g.nodes[node]["script"] = node_name.script
        g.nodes[node]["status"] = db_node.status.name

    return g


async def graph_from_edge_list_v2(
    edges: Sequence[Edge],
    session: AnyAsyncSession,
    node_type: type[Node] = Node,
    node_view: Literal["simple", "model"] = "model",
) -> nx.DiGraph:
    """Given a sequence of Edges, create a directed graph for these
    edges with nodes derived from database lookups of the related objects.

    Parameters
    ----------
    edges: Sequence[Edge]
        The list of edges forming the graph

    node_type: type
        The pydantic or sqlmodel class representing the graph node model

    node_view: "simple" or "model"
        Whether the node metadata in the graph should be simplified (dict) or
        using the full expunged model form.

    session
        An async database session
    """
    g = nx.DiGraph()
    g.add_edges_from([(e.source, e.target) for e in edges])
    relabel_mapping = {}

    # The graph understands the nodes in terms of the IDs used in the edges,
    # but we want to hydrate the entire Node model for subsequent users of this
    # graph to reference without dipping back to the Database.
    for node in g.nodes:
        db_node = await session.get_one(Node, node)
        # This Node is going on an adventure where it does not need to drag its
        # SQLAlchemy baggage along, so we expunge it from the session before
        # adding it to the graph.
        session.expunge(db_node)
        if node_view == "simple":
            # for the simple node view, the goal is to minimize the amount of
            # data attached to the node and ensure that this data is json-
            # serializable and otherwise appropriate for an API response
            g.nodes[node]["uuid"] = str(db_node.id)
            g.nodes[node]["name"] = db_node.name
            g.nodes[node]["status"] = db_node.status.name
            g.nodes[node]["kind"] = db_node.kind.name
            g.nodes[node]["version"] = db_node.version
            relabel_mapping[node] = f"{db_node.name}.{db_node.version}"
        else:
            g.nodes[node]["model"] = db_node

    if relabel_mapping:
        g = nx.relabel_nodes(g, mapping=relabel_mapping, copy=False)

    return g


def graph_to_dict(g: nx.DiGraph) -> Mapping:
    """Renders a networkx directed graph to a mapping format suitable for JSON
    serialization.

    Notes
    -----
    The "edges" attribute name in the node link data is "edges" instead of the
    default "links".
    """
    return nx.node_link_data(g, edges="edges")  # pyright: ignore[reportCallIssue]


def validate_graph(g: nx.DiGraph, source_name: str = "START", sink_name: str = "END") -> bool:
    """Validates a graph by asserting by traversal that a complete and correct
    path exists between `source` and `sink` nodes.

    "Correct" means that there are no cycles or isolate nodes (nodes with
    degree 0) and no nodes with degree 1.
    """
    try:
        # discover and check the source and sink nodes if given as a string
        source_nodes = [n[1].id for n in g.nodes(data="model") if n[1].name == source_name]  # pyright: ignore[reportArgumentType]
        sink_nodes = [n[1].id for n in g.nodes(data="model") if n[1].name == sink_name]  # pyright: ignore[reportArgumentType]
        if len(source_nodes) > 1:
            raise InvalidCampaignGraphError("Graph has more than one START node")
        elif len(source_nodes) < 1:
            raise InvalidCampaignGraphError("Graph has no START node")
        else:
            source = source_nodes[0]
        if len(sink_nodes) > 1:
            raise InvalidCampaignGraphError("Graph has more than one END node")
        elif len(sink_nodes) < 1:
            raise InvalidCampaignGraphError("Graph has no END node")
        else:
            sink = sink_nodes[0]
    except (AttributeError, KeyError):
        # Graph nodes data do not have a model component, which should only
        # occur in unit tests or when the graph has been serialized with a
        # "simple" view
        source = source_name
        sink = sink_name

    try:
        # Test that G is a directed graph with no cycles
        is_valid = nx.is_directed_acyclic_graph(g)
        assert is_valid

        # And that any path from source to sink exists
        is_valid = nx.has_path(g, source, sink)
        assert is_valid

        # Guard against bad graphs where START and/or END have been connected
        # such that they are no longer the only source and sink
        ...

        # Test that there are no isolated Nodes in the graph. A node becomes
        # isolated if it was involved with an edge that has been removed from
        # G with no replacement edge added, in which case the node should also
        # be removed.
        is_valid = nx.number_of_isolates(g) == 0
        assert is_valid

        # TODO Given the set of nodes in the graph, consider all paths in G
        #      from source to sink, making sure every node appears in a path?

        # Every node in G that is not the START/END node must have a degree
        # of at least 2 (one inbound and one outbound edge). If G has any
        # node with a degree of 1, it cannot be considered valid.
        g_degree_view: Iterable = nx.degree(g, (n for n in g.nodes if n not in [source, sink]))
        is_valid = min([d[1] for d in g_degree_view]) > 1
        assert is_valid
    except (nx.exception.NodeNotFound, AssertionError):
        return False
    return True


def processable_graph_nodes(g: nx.DiGraph) -> Iterable[Node]:
    """Traverse the graph G and produce an iterator of any nodes that are
    candidates for processing, i.e., their status is waiting/prepared/running
    and their ancestors are complete/successful. Graph nodes in a failed state
    will block the graph and prevent candidacy for subsequent nodes.

    Yields
    ------
    `lsst.cmservice.db.campaigns_v2.Node`
        A Node ORM object that has been ``expunge``d from its ``Session``.

    Notes
    -----
    This function operates only on valid graphs (see `validate_graph()`) that
    have been built by the `graph_from_edge_list_v2()` function, where each
    graph-node is decorated with a "model" attribute referring to an expunged
    instance of ``Node``. This ``Node`` can be ``add``ed back to a ``Session``
    and manipulated in the usual way.
    """
    processable_nodes: MutableSet[Node] = set()

    # A valid campaign graph will have only one source (START) with in_degree 0
    # and only one sink (END) with out_degree 0
    source = next(v for v, d in g.in_degree() if d == 0)
    sink = next(v for v, d in g.out_degree() if d == 0)

    # For each path through the graph, evaluate the state of nodes to determine
    # which nodes are up for processing. When there are multiple paths, we have
    # parallelization and common ancestors may be evaluated more than once,
    # which is an exercise in optimization left as a TODO
    for path in nx.all_simple_paths(g, source, sink):
        for n in path:
            node: Node = g.nodes[n]["model"]
            # A "script" considers "reviewable" a terminal status; nodes share
            # this opinion.
            if node.status.is_processable_script():
                processable_nodes.add(node)
                # We found a processable node in this path, stop traversal
                break
            elif node.status.is_bad():
                # We reached a failed node in this path, it is blocked
                break
            else:
                # This node must be in a "successful" terminal state
                continue

    # the inspection should stop when there are no more nodes to check
    yield from processable_nodes


async def insert_node_to_graph(
    node_0: UUID,
    node_1: UUID,
    *,
    namespace: UUID,
    session: AsyncSession | None = None,
    commit: bool = True,
) -> None:
    """Apply an insert operation to a graph by adding a new node_1 immediately
    adjacent to node_0 where all downstream node_0 edges are moved to node_1.

    ```
    A --> B  becomes  A --> X --> B

    A --> B  becomes A --> X --> B
      `-> C                  `-> C
    ```
    """
    if TYPE_CHECKING:
        assert session is not None

    s = select(Edge).with_for_update().where(Edge.source == node_0)
    adjacent_edges = (await session.exec(s)).all()

    # Move all the adjacent edges from node_0 to node_1
    for edge in adjacent_edges:
        edge.source = node_1
        edge.metadata_["mtime"] = element_time()

    # Make node_0 and node_1 adjacent
    new_adjacency_name = uuid4()
    new_adjacency = Edge(
        id=uuid5(namespace, new_adjacency_name.bytes),
        name=new_adjacency_name.hex,
        namespace=namespace,
        source=node_0,
        target=node_1,
    )
    session.add(new_adjacency)
    if commit:
        await session.commit()


async def append_node_to_graph(
    node_0: UUID,
    node_1: UUID,
    *,
    namespace: UUID,
    session: AsyncSession | None = None,
    commit: bool = True,
) -> None:
    """Apply an append operation to a graph by adding a new node_1 parallel
    to an existing node_0 where all adjacencies are copied to node_1.

    ```
    A --> B --> C  becomes  A --> B --> C
                              `-> X -/
    ```

    This behavior is appropriate for the common use case of adding group nodes
    in parallel to an "anchor" group node, such as the case where "B" was added
    to the graph as an "insert" and it is known that additional nodes must be
    parallel to it.

    Different contexts with different kinds of "anchor" nodes for this op
    require a different algorithm, for example the case of adding a "Step" node
    in parallel with an existing "Step" node that has already prepared its
    groups -- the new node should not form adjacencies with those groups!

    ```
    A --> B --> B1 --> Bx --> C
            `-> B2 -/
    ```

    In this case, appending a node X to B where Bn are its groups and Bx is its
    collect-step, X should be adjacent to C, not to B1 and B2:

    ```
    A ---> B --> B1 ---> Bx --> C
      `      `-> B2 -/      /
       `-> X --------------/
    ```

    In this case, when determining the "downstream edges" to inherit for the
    new node X, nodes of kind "group" and "collect" should be invisible to the
    algorithm.

    Other contexts may be unsupported or meaningless to the application, in
    which case the append request should abend with an error or a warning along
    with a no-op.

    For example, appending a node to a "collect-step" is not a meaningful oper-
    ation because there should only ever be one node adjacent to a set of group
    nodes. Likewise, no node should ever be made parallel to a "start" or "end"
    node as this would create an invalid graph. Future node kinds, for instance
    a "breakpoint" or "approval" node, would likewise not support append oper-
    ations as this would give the graph a way to bypass an intentional check-
    point.

    Raises
    ------
    NotImplementedError
        Raised if the node parallelization context is not supported or not yet
        implemented. It is left to the caller to decide how to proceed.
    """
    if TYPE_CHECKING:
        assert session is not None

    # define a context for this operation based on the node_0 kind.
    # FIXME if the function accepted a Node in addition to an ID, this
    # potentially extra select statement could be avoided.
    n_0 = await session.get_one(Node, ident=node_0)

    match n_0.kind:
        case ManifestKind.group | ManifestKind.step_group | ManifestKind.other:
            # create new "downstream" edges with node_1
            s = select(Edge).with_for_update().where(Edge.source == node_0)
            downstream_edges = (await session.exec(s)).all()
        case ManifestKind.grouped_step | ManifestKind.step:
            # node_1 should become adjacent to the next nodes in node_0's path
            # that are not a group or a collect node.
            # this ORM statement forms a recursive CTE for traversing a graph
            # starting at the edge for which node_0 is a source. The recursive
            # CTE returns all edges along the directed path from node_0, and
            # in the end we ignore edges involving nodes that are "invisible"
            # to this operation. The general form of this Query is
            #
            # WITH RECURSIVE ed AS (
            #  SELECT * from edges where source = node_0
            #  UNION
            #  SELECT * from edges JOIN ed on (edges.source = ed.target)
            # ) SELECT * from ed
            # join nodes on (edge.target = node.id)
            # where node.kind not in (...)
            cte = (
                select(
                    col(Edge.id).label("id"),
                    col(Edge.source).label("source"),
                    col(Edge.target).label("target"),
                )
                .where(Edge.source == node_0)
                .cte("ed", recursive=True)
            )
            next_valid_nodes = select(Edge.id, Edge.source, Edge.target).join(
                cte, col(Edge.source) == cte.c.target
            )
            s = (
                select(Edge)
                .join(cte.union(next_valid_nodes), col(Edge.id) == cte.c.id)
                .join(Node, col(Edge.target) == Node.id)
                .where(col(Node.kind).not_in([ManifestKind.group, ManifestKind.collect_groups]))
                .limit(1)
            )
            downstream_edge = (await session.exec(s)).one_or_none()
            if downstream_edge is None:
                raise RuntimeError
            # this edge is the "exit" of the target step-group's network of
            # groups via its collect-step, so to form "parallel" adjancencies
            # with the original step, we use this as a proxy for the node we
            # want to append.
            s = select(Edge).with_for_update().where(Edge.source == downstream_edge.source)
            downstream_edges = (await session.exec(s)).all()
        case ManifestKind.breakpoint | ManifestKind.start | ManifestKind.end:
            # node_1 may not become adjacent to these kinds of nodes; this is
            # not a default, this is a specific implementation decision.
            raise NotImplementedError
        case _:
            # Additional use cases may be added to this logic, but the default
            # fall-through case is an error.
            raise NotImplementedError

    # create new "upstream" edges with node_1
    s = select(Edge).with_for_update().where(Edge.target == node_0)
    upstream_edges = (await session.exec(s)).all()

    for edge in downstream_edges:
        session.expunge(edge)
        new_adjacency_name = uuid4()
        new_adjacency = Edge(
            id=uuid5(namespace, new_adjacency_name.bytes),
            name=new_adjacency_name.hex,
            namespace=namespace,
            source=node_1,
            target=edge.target,
        )
        session.add(new_adjacency)

    for edge in upstream_edges:
        session.expunge(edge)
        new_adjacency_name = uuid4()
        new_adjacency = Edge(
            id=uuid5(namespace, new_adjacency_name.bytes),
            name=new_adjacency_name.hex,
            namespace=namespace,
            source=edge.source,
            target=node_1,
        )
        session.add(new_adjacency)

    if commit:
        await session.commit()


async def delete_node_from_graph(
    node_0: UUID,
    *,
    namespace: UUID,
    session: AsyncSession | None = None,
    heal: bool = True,
    keep_node: bool = True,
    commit: bool = True,
) -> None:
    """Delete an existing node_0 with optional (but default) self-healing. The
    node is preserved unless keep_node is set to False. In either case, the
    primary objects subject to deletion are the Edges between nodes; this is
    not a "delete node from database" function.

    When healing, all successor edges for node_0 are re-established on all
    predecessor nodes.

    Examples
    --------
    Deleting Node B...

    ```
    A --> B --> C  becomes  A --> C
    ```

    ```
    A --> B --> C  becomes  A --> C
    AA /    `-> D             `-> D
                           AA --> C
                              `-> D
    ```

    Notes
    -----
    A harmless artifact appears when deleting a node in a parallel group with
    healing, which can become an error if multiple parallel nodes are deleted
    with heal, because multipaths are not allowed.

    When manipulating parallel paths, heal should be False except for a single
    element in the parallel group.

    Deleting Node B...

    ```
    A --> B --> C  becomes  A --------> C
      `-> D -/                `-> D -/
    ```

    Deleting Node D...
    ```
    A --------> C  becomes  A --------> C
      `-> D -/                `------/
    ```
    """
    if TYPE_CHECKING:
        assert session is not None

    s = select(Edge).with_for_update().where(Edge.source == node_0)
    downstream_edges = (await session.exec(s)).all()

    s = select(Edge).with_for_update().where(Edge.target == node_0)
    upstream_edges = (await session.exec(s)).all()

    # The list of predecessor nodes will reform downstream edges during heal
    predecessors: list[UUID] = []
    for edge in upstream_edges:
        predecessors.append(edge.source)
        await session.delete(edge)

    for edge in downstream_edges:
        await session.delete(edge)

        if heal:
            # create new edges that replicate the upstream edges to point to
            # the immediate predecessors
            for node_1 in predecessors:
                new_adjacency_name = uuid4()
                new_adjacency = Edge(
                    id=uuid5(namespace, new_adjacency_name.bytes),
                    name=new_adjacency_name.hex,
                    namespace=namespace,
                    source=node_1,
                    target=edge.target,
                )
                session.add(new_adjacency)

    if not keep_node:
        node = await session.get_one(Node, node_0, with_for_update=True)
        await session.delete(node)

    if commit:
        await session.commit()
