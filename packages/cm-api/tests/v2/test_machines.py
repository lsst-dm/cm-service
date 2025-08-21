"""Tests for State Machines."""

import pickle
import random
from unittest.mock import patch
from urllib.parse import urlparse
from uuid import UUID, uuid4, uuid5

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.api.machines.node import NodeMachine, StartMachine
from lsst.cmservice.api.machines.tasks import change_campaign_state
from lsst.cmservice.core.common.enums import StatusEnum
from lsst.cmservice.core.db.campaigns_v2 import Campaign, Machine, Node

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_node_machine(test_campaign: str, session: AsyncSession) -> None:
    """Test the critical/happy path of a node state machine."""

    # extract the test campaign id from the fixture url and determine the START
    # node id
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "START.1")

    node = await session.get_one(Node, node_id)
    x = node.status
    assert x is StatusEnum.waiting
    await session.commit()

    node_machine = StartMachine(o=node)
    assert node_machine.is_waiting()
    assert await node_machine.may_prepare()

    did_prepare = await node_machine.prepare()
    assert did_prepare
    assert await node_machine.may_start()

    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.ready
    await session.commit()

    did_start = await node_machine.start()
    assert did_start
    assert await node_machine.may_pause()
    assert await node_machine.may_finish()

    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.running
    await session.commit()

    did_finish = await node_machine.trigger("finish")
    assert did_finish
    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.accepted
    await session.commit()


async def test_bad_transition(test_campaign: str, session: AsyncSession) -> None:
    """Forces a state transition to raise an exception and tests the generation
    of an activity log record.
    """
    # extract the test campaign id from the fixture url
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "START.1")

    node = await session.get_one(Node, node_id)
    x = node.status
    assert x is StatusEnum.waiting
    await session.commit()

    node_machine = StartMachine(o=node)
    with patch(
        "lsst.cmservice.api.machines.node.StartMachine.do_prepare",
        side_effect=RuntimeError("Error: unknown error"),
    ):
        assert await node_machine.may_trigger("prepare")
        assert not await node_machine.trigger("prepare")

    # Failure to prepare should transition the node, and reset should recover
    assert node_machine.is_failed()
    assert node_machine.may_reset()
    assert await node_machine.reset()

    with patch(
        "lsst.cmservice.api.machines.node.StartMachine.do_prepare",
        return_value=None,
    ):
        assert await node_machine.prepare()
        assert await node_machine.start()

    # test the automatic transition to failure when an exception is raised in
    # the success check conditional callback
    with patch(
        "lsst.cmservice.api.machines.node.StartMachine.is_done_running",
        side_effect=RuntimeError("Error: WMS execution failure"),
    ):
        await node_machine.may_finish()

    # Both the state machine and db object should reflect the failed state
    assert node_machine.is_failed()
    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.failed
    await session.commit()

    # retry by rolling back to ready
    assert await node_machine.may_retry()
    await node_machine.trigger("retry")

    assert node_machine.is_ready()
    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.ready
    await session.commit()

    # start and finish without further error
    assert await node_machine.start()
    assert await node_machine.finish()

    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.accepted
    await session.commit()


async def test_machine_pickle(test_campaign: str, session: AsyncSession) -> None:
    """Tests the serialization of a state machine in and out of a pickle."""
    # extract the test campaign id from the fixture url
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "START.1")

    node = await session.get_one(Node, node_id)
    x = node.status
    assert x is StatusEnum.waiting
    await session.commit()

    node_machine = NodeMachine(o=node)
    # evolve the machine to "prepared"
    await node_machine.prepare()
    assert node_machine.state is StatusEnum.ready

    # pickles can go to the database
    machine_pickle = pickle.dumps(node_machine.machine)
    machine_db = Machine.model_validate(dict(id=uuid4(), state=machine_pickle))

    # campaigns can have a reference to their machine, but the machine ids are
    # not necessarily deterministic (i.e., they do not have to be namespaced.)
    session.add(machine_db)
    node.machine = machine_db.id
    await session.commit()

    await session.close()
    del node_machine
    del node
    del machine_db
    del machine_pickle

    # get new objects from the database
    new_node = await session.get_one(Node, node_id)
    machine_unpickle = await session.get_one(Machine, new_node.machine)

    # Before pickling, the stateful model had the machine as its `.machine`
    # member, and the machine itself had the stateful model as its `.model`
    # member. To get back where we started, we would want to use the unpickled
    # machine's `.model` attribute as our first-class named object, then re-
    # assign any members we had to disasssociate before pickling
    assert machine_unpickle.state is not None
    new_node_machine: NodeMachine = (pickle.loads(machine_unpickle.state)).model
    new_node_machine.db_model = new_node

    # test the rehydrated machine and continue to evolve it
    assert new_node_machine.state == new_node.status
    await session.commit()

    await new_node_machine.start()
    await session.refresh(new_node, attribute_names=["status"])
    assert new_node_machine.state == new_node.status
    await session.commit()

    await new_node_machine.finish()
    await session.refresh(new_node, attribute_names=["status"])
    assert new_node_machine.state == new_node.status
    await session.commit()


async def test_change_campaign_state(
    session: AsyncSession, aclient: AsyncClient, test_campaign: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests that the campaign state change background task sets a campaign
    status when it is supposed to, and does not when it is not.
    """
    # the test_campaign fixture produces a valid graph so it should be possible
    # to set the campaign to running, then paused
    # extract the test campaign id from the fixture url
    edge_list = (await aclient.get(test_campaign)).json()

    campaign_id = urlparse(test_campaign).path.split("/")[-2:][0]
    campaign = await session.get_one(Campaign, campaign_id)
    await session.commit()

    x = (await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}")).json()
    assert x["status"] == "waiting"

    await change_campaign_state(campaign, StatusEnum.running, uuid4())
    await session.refresh(campaign, attribute_names=["status"])
    await session.commit()

    x = (await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}")).json()
    assert x["status"] == "running"

    await change_campaign_state(campaign, StatusEnum.paused, uuid4())
    await session.refresh(campaign, attribute_names=["status"])
    await session.commit()

    x = (await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}")).json()
    assert x["status"] == "paused"

    # Break the graph by removing an edge from the campaign, and try to enter
    # the running state
    edge_to_remove = random.choice(edge_list)["id"]
    x = await aclient.delete(f"/cm-service/v2/edges/{edge_to_remove}")

    caplog.clear()
    await change_campaign_state(campaign, StatusEnum.running, uuid4())
    await session.refresh(campaign, attribute_names=["status"])
    await session.commit()

    x = (await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}")).json()
    assert x["status"] == "paused"

    # Check log messages
    log_entry_found = False
    for r in caplog.records:
        if "InvalidCampaignGraphError" in r.message:
            log_entry_found = True
            break
    assert log_entry_found
