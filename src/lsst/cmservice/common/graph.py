from collections.abc import Mapping, Sequence
from typing import TypeVar

import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from ..db import Script, ScriptDependency, Step, StepDependency
from ..parsing.string import parse_element_fullname

A = TypeVar("A", async_scoped_session, AsyncSession)
N = TypeVar("N", type[Step], type[Script])


async def graph_from_edge_list(
    edges: Sequence[StepDependency | ScriptDependency], node_type: N, session: A
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


def graph_to_dict(g: nx.DiGraph) -> Mapping:
    """Renders a networkx directed graph to a mapping format suitable for JSON
    serialization.
    """
    return nx.node_link_data(g, edges="edges")
