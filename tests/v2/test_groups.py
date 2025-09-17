from collections import ChainMap
from itertools import pairwise
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import urlparse
from uuid import UUID, uuid4, uuid5

import networkx as nx
import numpy as np
import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.common.enums import DEFAULT_NAMESPACE, ManifestKind
from lsst.cmservice.common.graph import validate_graph
from lsst.cmservice.db.campaigns_v2 import Node
from lsst.cmservice.machines.node import GroupMachine, StepMachine

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


@patch("lsst.cmservice.common.splitter.QuerySplitter.butler_query", return_value=np.arange(3_932_128))
async def test_campaign_with_groups(
    MockSplitter: Mock, test_campaign_groups: str, session: AsyncSession
) -> None:
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Prepare a step with no grouping
    node_id = uuid5(UUID(campaign_id), "lambert.1")

    node = await session.get_one(Node, node_id)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Prepare a step with values-based grouping
    node_id = uuid5(UUID(campaign_id), "ash.1")

    node = await session.get_one(Node, node_id)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Prepare a step with query grouping
    node_id = uuid5(UUID(campaign_id), "ripley.1")

    node = await session.get_one(Node, node_id)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    ...

    # Rollback the prepare trigger
    await node_machine.trigger("unprepare")

    ...


async def test_append_node_to_prepared_step(
    aclient: AsyncClient, session: AsyncSession, test_campaign_groups: str
) -> None:
    """Tests the manipulation of a campaign graph by appending a new node to a
    prepared "Step", which should find a downstream node that is neither a
    "group" nor a "collect" step.
    """
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Prepare a step with values-based grouping
    node_0_id = uuid5(UUID(campaign_id), "ash.1")

    node = await session.get_one(Node, node_0_id)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

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

    # Get and assemble post-modification campaign graph
    graph_url = test_campaign_groups.replace("/edges", "/graph")
    x = await aclient.get(graph_url)
    assert x.is_success

    # Test valid reconstruction of the graph
    graph: nx.DiGraph = nx.node_link_graph(x.json(), edges="edges")  # pyright: ignore[reportCallIssue]
    assert validate_graph(graph, source_name="START.1", sink_name="END.1")

    # Test that the new "node_1" was made parallel to "ash.1" by asserting that
    # node_1 and ash's collect step have exactly the same downstream
    assert set(graph.successors("node_1.1")) == set(graph.successors("ash_collect_groups.1"))

    # And that "node_1" and "ash" have exactly the same upstream
    assert set(graph.predecessors("node_1.1")) == set(graph.predecessors("ash.1"))


async def test_array_splitting() -> None:
    """Test demonstrates the partitioning of an arbitrarily large np array via
    partial sorting.
    """
    dimension = "field"
    d = np.arange(932_673)
    np.random.shuffle(d)

    group_size = min(100_000, d.size // 8)
    group_count = (d.size // group_size) + (d.size % group_size != 0)
    partition_indices = np.linspace(0, d.size, num=group_count, dtype=int, endpoint=False)

    d.partition(partition_indices)

    predicates = []
    for a, b in pairwise(partition_indices):
        predicates.append(f"{dimension} >= {d[a]} AND {dimension} < {d[b]}")
    predicates.append(f"{dimension} >= {d[partition_indices[-1]]}")

    assert len(predicates) == 10
    assert predicates[0] == f"{dimension} >= 0 AND {dimension} < 93267"
    assert predicates[-1] == f"{dimension} >= 839405"


async def test_bps_stdout_parsing(session: AsyncSession) -> None:
    """Tests the bps stdout parsing behavior of a GroupMachine"""
    node = Node(
        id=uuid4(),
        name="group_node",
        namespace=DEFAULT_NAMESPACE,
        version=1,
        kind=ManifestKind.group,
        metadata_={},
    )
    session.add(node)
    await session.commit()

    event = MagicMock()
    event.transition.source = "running"
    event.transition.dest = "running"

    # Test the successful case
    bps = {"stdout_log": str(Path(__file__).parent.parent / "fixtures/bps/bps_stdout.log")}
    machine = GroupMachine(o=node)
    machine.session = session
    machine.configuration_chain = {"bps": ChainMap(bps)}

    await machine.capture_bps_stdout(event)
    await session.commit()
    assert node.metadata_["bps"].get("Submit dir") is not None

    # Test the missing file case
    bps = {"stdout_log": str(Path(__file__).parent.parent / "fixtures/bps/missing_stdout.log")}
    machine = GroupMachine(o=node)
    machine.session = session
    machine.configuration_chain = {"bps": ChainMap(bps)}

    await machine.capture_bps_stdout(event)
    await session.commit()
    assert node.metadata_["bps"].get("Submit dir") is None
