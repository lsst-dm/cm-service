"""tests for the v2 daemon"""

from urllib.parse import urlparse
from uuid import uuid5

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.common.daemon_v2 import consider_campaigns, consider_nodes
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.db.campaigns_v2 import Campaign, Node, Task

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_daemon_campaign(
    caplog: pytest.LogCaptureFixture, test_campaign: str, session: AsyncSession
) -> None:
    """Tests the handling of campaigns during daemon iteration, which is
    primarily done by checking side effects. This test assesses a test campaign
    with three nodes and asserts that node(s) are added to the Task table in
    the correct order and that as they enter an accepted state the daemon can
    continue to traverse the campaign graph and visit more nodes until the
    END node is reached.
    """

    # At first, the test_campaign in a waiting state is not subject to daemon
    # consideration
    caplog.clear()
    await consider_campaigns(session)

    # extract the test campaign id from the fixture url
    campaign_id = urlparse(test_campaign).path.split("/")[-2:][0]

    campaign = await session.get_one(Campaign, campaign_id)
    assert campaign.status is not None
    x = campaign.status
    assert x is StatusEnum.waiting

    # check the next state in the happy path and set the campaign status
    # (i.e., without using the Campaign FSM)
    assert campaign.status.next_status() is StatusEnum.ready
    campaign.status = campaign.status.next_status()
    await session.commit()

    # now the daemon should consider the prepared campaign
    caplog.clear()
    await consider_campaigns(session)
    found_log_messages = 0
    for r in caplog.records:
        if any(["considering campaign" in r.message, "considering node" in r.message]):
            found_log_messages += 1
    assert found_log_messages == 2

    # A task should now be in the task table
    tasks = (await session.exec(select(Task))).all()
    assert len(tasks) == 1

    # Fetch the node, set it to a terminal status, and consider the campaign
    # again
    node = await session.get_one(Node, tasks[0].node)
    assert node.name == "START"
    node.status = StatusEnum.accepted
    await session.commit()

    caplog.clear()
    await consider_campaigns(session)
    tasks = (await session.exec(select(Task))).all()
    # One additional task should be in the table now
    assert len(tasks) == 2
    node = await session.get_one(Node, tasks[-1].node)
    node.status = StatusEnum.accepted
    await session.commit()

    # The next assessment should produce two nodes to be handled in parallel
    caplog.clear()
    await consider_campaigns(session)
    tasks = (await session.exec(select(Task))).all()
    # Two additional tasks should be in the table now
    assert len(tasks) == 4

    node = await session.get_one(Node, tasks[-1].node)
    node.status = StatusEnum.accepted
    node = await session.get_one(Node, tasks[-2].node)
    node.status = StatusEnum.accepted
    await session.commit()

    # The next assessment should produce the END node
    caplog.clear()
    await consider_campaigns(session)
    tasks = (await session.exec(select(Task))).all()
    # One additional task should be in the table now
    assert len(tasks) == 5
    node = await session.get_one(Node, tasks[-1].node)
    assert node.name == "END"
    node.status = StatusEnum.accepted
    await session.commit()


async def test_daemon_node(
    caplog: pytest.LogCaptureFixture, test_campaign: str, session: AsyncSession
) -> None:
    # set the campaign to running (without involving a campaign machine)
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    campaign = await session.get_one(Campaign, campaign_id)
    campaign.status = StatusEnum.running
    await session.commit()

    # after the equivalent of a single iteration, the test campaign's START
    # Node will be on the task list with a transition from waiting->ready.
    await consider_campaigns(session)
    await consider_nodes(session)

    ...

    # As we continue to iterate the daemon over the campaign's 5 nodes
    # (including its START and END), each node in the graph is evolved.
    # To simulate this, we'll pull the END node from the database and wait
    # until it is in its terminal "accepted" state.
    end_node = await session.get_one(Node, uuid5(campaign.id, "END.1"))

    # set up a release valve to stave off infinite loops in case things don't
    # go well. This should take 11 iterations (4 nodes * 3 transitions, one of
    # which is already done.)
    i = 12
    while end_node.status is not StatusEnum.accepted:
        i -= 1
        await consider_campaigns(session)
        await consider_nodes(session)
        # the end node is expunged from the session as a side effect when the
        # graph is built
        session.add(end_node)
        await session.refresh(end_node, attribute_names=["status"])
        if not i:
            raise RuntimeError("Node evolution took too long")

    ...


def test_dynamic_node_machine() -> None:
    """Test the dynamic resolution of a ``NodeMachine`` class based on a Node's
    ``kind`` attribute.
    """
    from lsst.cmservice.common.enums import ManifestKind
    from lsst.cmservice.machines.node import GroupMachine, NodeMachine, node_machine_factory

    k = ManifestKind.node
    x = node_machine_factory(k)
    assert x is NodeMachine

    k = ManifestKind.group
    x = node_machine_factory(k)
    assert x is GroupMachine
