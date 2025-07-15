"""Tests graph operations using v2 objects"""

import networkx as nx
import pytest
from httpx import AsyncClient

from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.common.graph import graph_from_edge_list_v2, processable_graph_nodes, validate_graph
from lsst.cmservice.common.types import AnyAsyncSession
from lsst.cmservice.db.campaigns_v2 import Edge

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_build_and_walk_graph(
    aclient: AsyncClient, session: AnyAsyncSession, test_campaign: str
) -> None:
    """Test the generation and traversal of a campaign graph as created in the
    ``test_campaign`` fixture.

    Test that the graph is traversed from START to END in order, and that as
    graph nodes are "processable" they can be handled. In this test, the status
    of each node is set to "accepted" and updated in the databse. The campaign
    graph is recreated between each stage of the mock graph processing.

    The test campaign is a set of 3 nodes arranged in a graph:

    ```
    START --> A --> B --> END
                --> C -->
    ```
    """
    edge_list = [Edge.model_validate(edge) for edge in (await aclient.get(test_campaign)).json()]
    graph = await graph_from_edge_list_v2(edge_list, session)

    # the START node should be the only processable Node
    for node in processable_graph_nodes(graph):
        assert node.name == "START"
        assert node.status is StatusEnum.waiting
        # Add the Node back to the session and update its status
        session.add(node)
        await session.refresh(node)
        node.status = StatusEnum.accepted
        await session.commit()

    # Repeat the graph building and traversal, this time expecting a single
    # node that is not "START"
    graph = await graph_from_edge_list_v2(edge_list, session)
    for node in processable_graph_nodes(graph):
        assert node.name != "START"
        assert node.status is StatusEnum.waiting
        # Add the Node back to the session and update its status
        session.add(node)
        await session.refresh(node)
        node.status = StatusEnum.accepted
        await session.commit()

    # Repeat the graph building and traversal, this time expecting a pair of
    # nodes processable in parallel
    graph = await graph_from_edge_list_v2(edge_list, session)
    count = 0
    for node in processable_graph_nodes(graph):
        count += 1
        assert node.name != "START"
        assert node.status is StatusEnum.waiting
        # Add the Node back to the session and update its status
        session.add(node)
        await session.refresh(node)
        node.status = StatusEnum.accepted
        await session.commit()
    assert count == 2

    # Finally, expect the END node
    graph = await graph_from_edge_list_v2(edge_list, session)
    for node in processable_graph_nodes(graph):
        assert node.name == "END"
        assert node.status is StatusEnum.waiting
        # Add the Node back to the session and update its status
        session.add(node)
        await session.refresh(node)
        node.status = StatusEnum.accepted
        await session.commit()


def test_validate_graph() -> None:
    """Test basic graph validation operations using a simple DAG."""
    edge_list = [("A", "B"), ("B", "C"), ("C", "D"), ("C", "E"), ("D", "F"), ("E", "F")]

    g = nx.DiGraph()
    g.add_edges_from(edge_list)

    # this is a valid graph
    assert validate_graph(g, "A", "F")

    # add a new parallel node with no path to sink
    g.add_edge("C", "CC")
    assert not validate_graph(g, "A", "F")

    # create a cycle with the new node
    g.add_edge("CC", "A")
    assert not validate_graph(g, "A", "F")

    # correct the path
    g.remove_edge("CC", "A")
    g.add_edge("CC", "F")
    assert validate_graph(g, "A", "F")

    # remove the edges from a node
    g.remove_edge("CC", "F")
    g.remove_edge("C", "CC")
    # the graph is invalid because "CC" is now an isolate
    assert not validate_graph(g, "A", "F")

    # remove the unneeded node
    g.remove_node("CC")
    assert validate_graph(g, "A", "F")


async def test_campaign_graph_route(aclient: AsyncClient, test_campaign: str) -> None:
    """Tests the acquisition of a serialized graph from a REST endpoint and
    the subsequent reconstruction of a valid graph from the node-link data.
    """
    graph_url = test_campaign.replace("/edges", "/graph")
    x = await aclient.get(graph_url)
    assert x.is_success

    # Test reconstruction of the serialized graph
    graph = nx.node_link_graph(x.json(), edges="edges")
    assert validate_graph(graph)
