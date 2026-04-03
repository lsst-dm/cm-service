from collections.abc import Sequence
from warnings import deprecated

import networkx as nx

from lsst.cmservice.models.types import AnyAsyncSession

from ..db import Script, ScriptDependency, Step, StepDependency
from ..parsing.string import parse_element_fullname

type AnyGraphEdge = StepDependency | ScriptDependency
type AnyGraphNode = Step | Script


@deprecated("This function is used for CM v1, use graph_from_edge_list_v2 instead")
async def graph_from_edge_list(
    edges: Sequence[AnyGraphEdge],
    node_type: type[AnyGraphNode],
    session: AnyAsyncSession,
) -> nx.DiGraph:
    """Given a sequence of edge-tuples, create a directed graph for these
    edges with nodes derived from database lookups of the related objects.
    """
    g: nx.DiGraph = nx.DiGraph()
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
