from collections.abc import Iterable, Mapping, MutableSet, Sequence
from typing import Literal
from uuid import UUID

import networkx as nx

from ..db import Script, ScriptDependency, Step, StepDependency
from ..db.campaigns_v2 import Edge, Node
from ..parsing.string import parse_element_fullname
from .types import AnyAsyncSession

type AnyGraphEdge = StepDependency | ScriptDependency
type AnyGraphNode = Step | Script


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
            g.nodes[node]["id"] = str(db_node.id)
            g.nodes[node]["status"] = db_node.status.name
            g.nodes[node]["kind"] = db_node.kind.name
            relabel_mapping[node] = db_node.name
        else:
            g.nodes[node]["model"] = db_node

    if relabel_mapping:
        g = nx.relabel_nodes(g, mapping=relabel_mapping, copy=False)

    # TODO validate graph now raise exception, or leave it to the caller?
    return g


def graph_to_dict(g: nx.DiGraph) -> Mapping:
    """Renders a networkx directed graph to a mapping format suitable for JSON
    serialization.

    Notes
    -----
    The "edges" attribute name in the node link data is "edges" instead of the
    default "links".
    """
    return nx.node_link_data(g, edges="edges")


def validate_graph(g: nx.DiGraph, source: UUID | str = "START", sink: UUID | str = "END") -> bool:
    """Validates a graph by asserting by traversal that a complete and correct
    path exists between `source` and `sink` nodes.

    "Correct" means that there are no cycles or isolate nodes (nodes with
    degree 0) and no nodes with degree 1.
    """
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
            if node.status.is_processable_element():
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
