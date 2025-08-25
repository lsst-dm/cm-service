"""Tests graph operations using v2 objects"""

import random
from urllib.parse import urlparse
from uuid import UUID

import networkx as nx
import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.common.graph import (
    delete_node_from_graph,
    graph_from_edge_list_v2,
    processable_graph_nodes,
    validate_graph,
)
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


@pytest.mark.skip("fixed in DM-52178")
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


async def test_replace_node_in_graph(aclient: AsyncClient, test_campaign: str) -> None:
    """Test the manipulation of a campaign graph by changing a node in-place"""
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]

    # pick a random node from the campaign
    r = await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}/nodes")
    node_0_id = random.choice([n["id"] for n in r.json() if n["name"] not in ("START", "END")])

    # create a new Node in the campaign
    r = await aclient.post(
        "/cm-service/v2/nodes",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "node",
            "metadata": {"name": "node_1", "namespace": campaign_id},
            "spec": {},
        },
    )
    assert r.is_success
    node_1_id = r.json()["id"]

    # replace an existing node in the graph with the new one
    r = await aclient.put(
        f"/cm-service/v2/campaigns/{campaign_id}/graph/nodes/{node_0_id}?with-node={node_1_id}",
    )
    assert r.is_success

    # validate the old node is no longer in the graph but the new one is
    r = await aclient.get(test_campaign.replace("/edges", "/graph"))
    graph = r.json()
    f1 = filter(lambda n: 1 if n["uuid"] == node_0_id else 0, graph["nodes"])
    f2 = filter(lambda n: 1 if n["uuid"] == node_1_id else 0, graph["nodes"])
    assert not len(list(f1))
    assert len(list(f2))


async def test_insert_node_in_graph(
    aclient: AsyncClient, session: AnyAsyncSession, test_campaign: str
) -> None:
    """Tests the manipulation of a campaign graph by inserting a new node."""
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]

    # pick a random node from the campaign
    r = await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}/nodes")
    campaign_nodes = r.json()
    node_0_id = random.choice([n["id"] for n in campaign_nodes if n["name"] not in ("START", "END")])

    # create a new Node in the campaign
    r = await aclient.post(
        "/cm-service/v2/nodes",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "node",
            "metadata": {"name": "node_1", "namespace": campaign_id},
            "spec": {},
        },
    )
    assert r.is_success
    node_1_id = r.json()["id"]

    # INSERT the new node in the campaign downstream of Node_0
    r = await aclient.patch(
        f"/cm-service/v2/campaigns/{campaign_id}/graph/nodes/{node_0_id}?add-node={node_1_id}&operation=insert",
    )
    assert r.is_success

    # read and construct the updated campaign graph:
    edge_list = [Edge.model_validate(edge) for edge in (await aclient.get(test_campaign)).json()]
    graph = await graph_from_edge_list_v2(edge_list, session)

    # validate that node_0 is now adjacent only to node_1
    node_0 = UUID(node_0_id)
    node_1 = UUID(node_1_id)
    assert graph.has_node(node_0)
    assert graph.has_node(node_1)
    assert list(graph.successors(node_0)) == [node_1]


@pytest.mark.skip("Fixed in DM-52178")
async def test_append_node_in_graph(
    aclient: AsyncClient, session: AnyAsyncSession, test_campaign: str
) -> None:
    """Tests the manipulation of a campaign graph by appending a new node."""
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]

    # pick a random node from the campaign
    r = await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}/nodes")
    campaign_nodes = r.json()
    node_0_id = random.choice([n["id"] for n in campaign_nodes if n["name"] not in ("START", "END")])

    # create a new Node in the campaign
    r = await aclient.post(
        "/cm-service/v2/nodes",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "node",
            "metadata": {"name": "node_1", "namespace": campaign_id},
            "spec": {},
        },
    )
    assert r.is_success
    node_1_id = r.json()["id"]

    # APPEND the new node in the campaign parallel to Node_0
    r = await aclient.patch(
        f"/cm-service/v2/campaigns/{campaign_id}/graph/nodes/{node_0_id}?add-node={node_1_id}&operation=append",
    )
    assert r.is_success

    # read and construct the updated campaign graph:
    edge_list = [Edge.model_validate(edge) for edge in (await aclient.get(test_campaign)).json()]
    graph = await graph_from_edge_list_v2(edge_list, session)

    # validate that node_1 is now parallel to node_0
    node_0 = UUID(node_0_id)
    node_1 = UUID(node_1_id)
    assert graph.has_node(node_0)
    assert graph.has_node(node_1)

    assert set(graph.successors(node_0)) == set(graph.successors(node_1))
    assert set(graph.predecessors(node_0)) == set(graph.predecessors(node_1))

    # Get the start or end node
    meta_node_id = random.choice([n["id"] for n in campaign_nodes if n["name"] in ("START", "END")])
    # Try and fail to APPEND a new node parallel to the start or end
    r = await aclient.patch(
        f"/cm-service/v2/campaigns/{campaign_id}/graph/nodes/{meta_node_id}?add-node={node_1_id}&operation=append",
    )
    assert r.is_client_error


async def test_delete_node_from_graph(
    aclient: AsyncClient, session: AsyncSession, test_campaign: str
) -> None:
    """Tests the manipulation of a campaign graph by deleting a node."""
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]

    edge_list = [Edge.model_validate(edge) for edge in (await aclient.get(test_campaign)).json()]
    graph = await graph_from_edge_list_v2(edge_list, session)

    start_node = [n[0] for n in graph.degree if n[1] == 1][0]  # pyright: ignore[reportGeneralTypeIssues]

    # node A is the only neighbor of the START Node
    node_a = next(nx.all_neighbors(graph, start_node))

    # delete node A from the graph with healing, sacrificing the node
    await delete_node_from_graph(
        node_0=node_a,
        namespace=UUID(campaign_id),
        session=session,
        heal=True,
        keep_node=False,
        commit=True,
    )
    ...
