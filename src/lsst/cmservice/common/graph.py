from collections.abc import Iterable, Mapping, MutableSet, Sequence
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4, uuid5

import networkx as nx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

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
            g.nodes[node]["status"] = db_node.status.name
            g.nodes[node]["kind"] = db_node.kind.name
            g.nodes[node]["version"] = db_node.version
            relabel_mapping[node] = db_node.name
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
    """
    if TYPE_CHECKING:
        assert session is not None

    # create new "downstream" edges with node_1
    s = select(Edge).with_for_update().where(Edge.source == node_0)
    downstream_edges = (await session.exec(s)).all()

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
