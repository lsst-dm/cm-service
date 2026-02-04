"""Tests for State Machines."""

import pickle
import random
from asyncio import sleep
from pathlib import Path
from textwrap import dedent
from typing import cast
from unittest.mock import Mock, patch
from urllib.parse import urlparse
from uuid import UUID, uuid4, uuid5

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import make_transient, selectinload
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.common.enums import ManifestKind, StatusEnum
from lsst.cmservice.common.launchers import LauncherCheckResponse
from lsst.cmservice.db.campaigns_v2 import Campaign, Machine, Node
from lsst.cmservice.handlers.interface import get_activity_log_errors
from lsst.cmservice.machines.node import (
    GroupMachine,
    NodeMachine,
    StartMachine,
    StepCollectMachine,
    StepMachine,
)
from lsst.cmservice.machines.tasks import change_campaign_state

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


@patch("lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.launch", return_value=None)
@patch(
    "lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.check",
    return_value=LauncherCheckResponse(success=True),
)
async def test_node_machine(
    mock_check: Mock, mock_launch: Mock, test_campaign: str, session: AsyncSession
) -> None:
    """Test the critical/happy path of a node state machine."""
    # extract the test campaign id from the fixture url and determine the START
    # node id
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "START.1")

    node = await session.get_one(Node, node_id)
    x = node.status
    assert x is StatusEnum.waiting
    await session.commit()
    make_transient(node)
    node_machine = StartMachine(o=node)
    del node

    assert node_machine.is_waiting()
    assert await node_machine.may_prepare()

    did_prepare = await node_machine.prepare()
    assert did_prepare
    assert await node_machine.may_start()

    node = await session.get_one(Node, node_id)
    x = node.status
    assert x is StatusEnum.ready

    did_start = await node_machine.start()
    assert did_start
    assert await node_machine.may_pause()
    assert await node_machine.may_finish()

    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.running

    did_finish = await node_machine.trigger("finish")
    assert did_finish

    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.accepted


@patch("lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.launch", return_value=None)
@patch(
    "lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.check",
    return_value=LauncherCheckResponse(success=True),
)
async def test_bad_transition(
    mock_check: Mock, mock_launch: Mock, test_campaign: str, session: AsyncSession
) -> None:
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
    make_transient(node)
    node_machine = StartMachine(o=node)
    del node

    with patch(
        "lsst.cmservice.machines.node.StartMachine.do_prepare",
        side_effect=RuntimeError("Error: unknown error"),
    ):
        assert await node_machine.may_trigger("prepare")
        assert not await node_machine.trigger("prepare")

    # Failure to prepare should transition the node, and reset should recover
    assert node_machine.is_failed()
    assert await node_machine.may_reset()
    assert await node_machine.reset()

    with patch(
        "lsst.cmservice.machines.node.StartMachine.do_prepare",
        return_value=None,
    ):
        assert await node_machine.prepare()
        assert await node_machine.start()

    # test the automatic transition to failure when an exception is raised in
    # the success check conditional callback
    with patch(
        "lsst.cmservice.machines.node.StartMachine.is_done_running",
        side_effect=RuntimeError("Error: WMS execution failure"),
    ):
        await node_machine.may_finish()

    # Both the state machine and db object should reflect the failed state
    assert node_machine.is_failed()
    node = await session.get_one(Node, node_id)
    x = node.status
    assert x is StatusEnum.failed

    # retry by rolling back to ready
    assert await node_machine.may_retry()
    await node_machine.trigger("retry")

    assert node_machine.is_ready()
    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.ready

    # start and finish without further error
    assert await node_machine.start()
    assert await node_machine.finish()

    await session.refresh(node, attribute_names=["status"])
    x = node.status
    assert x is StatusEnum.accepted


async def test_machine_pickle(test_campaign: str, session: AsyncSession) -> None:
    """Tests the serialization of a state machine in and out of a pickle."""
    # extract the test campaign id from the fixture url
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "START.1")

    node = await session.get_one(Node, node_id)
    x = node.status
    assert x is StatusEnum.waiting
    await session.commit()
    make_transient(node)
    node_machine = NodeMachine(o=node)
    del node

    # evolve the machine to "prepared"
    await node_machine.prepare()
    assert node_machine.state is StatusEnum.ready

    # pickles can go to the database
    machine_pickle = pickle.dumps(node_machine.machine)
    machine_db = Machine.model_validate(dict(id=uuid4(), state=machine_pickle))

    # campaigns can have a reference to their machine, but the machine ids are
    # not necessarily deterministic (i.e., they do not have to be namespaced.)
    session.add(machine_db)
    node = await session.get_one(Node, node_id)
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

    await change_campaign_state(campaign, StatusEnum.running, str(uuid4()))
    await session.refresh(campaign, attribute_names=["status"])
    await session.commit()

    x = (await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}")).json()
    assert x["status"] == "running"

    await change_campaign_state(campaign, StatusEnum.paused, str(uuid4()))
    await session.refresh(campaign, attribute_names=["status"])
    await session.commit()

    x = (await aclient.get(f"/cm-service/v2/campaigns/{campaign_id}")).json()
    assert x["status"] == "paused"

    # Break the graph by removing an edge from the campaign, and try to enter
    # the running state
    edge_to_remove = random.choice(edge_list)["id"]
    x = await aclient.delete(f"/cm-service/v2/edges/{edge_to_remove}")

    caplog.clear()
    await change_campaign_state(campaign, StatusEnum.running, str(uuid4()))
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


async def test_action_node_htcondor(test_campaign_groups: str, session: AsyncSession) -> None:
    """Tests the operation of an Action node with HTCondor WMS Mixin."""

    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Prepare the start step
    node_id = uuid5(UUID(campaign_id), "START.1")
    node = await session.get_one(Node, node_id)
    await session.commit()
    make_transient(node)
    start_machine = StartMachine(o=node)
    del node
    await start_machine.trigger("prepare")

    # Prepare a step with null-based grouping
    node_id = uuid5(UUID(campaign_id), "lambert.1")
    node = await session.get_one(Node, node_id)
    node_machine = StepMachine(o=node)
    await session.commit()
    await node_machine.trigger("prepare")

    # Prepare a step with values-based grouping
    node_id = uuid5(UUID(campaign_id), "ash.1")
    node = await session.get_one(Node, node_id)
    node_machine = StepMachine(o=node)
    await session.commit()
    await node_machine.trigger("prepare")

    # Obtain one of the prepared groups
    s = select(Node).where(Node.kind == ManifestKind.group).where(Node.namespace == campaign_id).limit(1)
    group = (await session.exec(s)).one_or_none()
    assert group is not None

    # Obtain the collect step
    s = (
        select(Node)
        .where(Node.kind == ManifestKind.collect_groups)
        .where(Node.namespace == campaign_id)
        .limit(1)
    )
    collect = (await session.exec(s)).one_or_none()
    assert collect is not None

    group_machine = GroupMachine(o=group)
    await group_machine.trigger("prepare")
    assert len(await get_activity_log_errors(session, campaign_id)) == 0

    collect_machine = StepCollectMachine(o=collect)
    await collect_machine.trigger("prepare")
    assert len(await get_activity_log_errors(session, campaign_id)) == 0


async def test_group_config_chain(test_campaign_groups: str, session: AsyncSession) -> None:
    """Tests that a prepared group has the correct config chain lookup"""
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Fetch a step
    node_id = uuid5(UUID(campaign_id), "lambert.1")
    node = await session.get_one(Node, node_id)

    # Add step-specific configuration
    node.configuration["butler"] = {}
    node.configuration["butler"]["predicates"] = [
        "exposure >= 1234567890",
        "exposure < 2345678901",
    ]
    await session.commit()

    # Prepare the step
    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Fetch the group
    s = select(Node).where(Node.name == "lambert_group_001").where(Node.namespace == campaign_id)
    group = (await session.exec(s)).one()

    # Check group's configuration
    predicates = group.configuration.get("butler", {}).get("predicates", [])

    # campaign-level predicates
    assert "instrument='NOSTROMO'" in predicates

    # step-specific predicates
    assert "exposure >= 1234567890" in predicates
    assert "exposure < 2345678901" in predicates

    # group-specific predicate
    assert "(1=1)" in predicates


async def test_group_prepare_replace(
    test_campaign_groups: str, session: AsyncSession, aclient: AsyncClient
) -> None:
    """Tests the replacement of a node after its preparation and that group
    artifact paths do not interfere with each other.
    """
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Fetch and prepare a step
    node_id = uuid5(UUID(campaign_id), "lambert.1")
    node = await session.get_one(Node, node_id)
    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Fetch and prepare a group
    s = (
        select(Node)
        .where(Node.name == "lambert_group_001")
        .where(Node.namespace == campaign_id)
        .where(Node.version == 1)
    )

    group = (await session.exec(s)).one()
    group_machine = GroupMachine(o=group)
    await group_machine.trigger("prepare")

    # Assert the artifact path exists
    group_path = group.metadata_.get("artifact_path")
    assert group_path is not None
    assert Path(group_path).exists()

    # Replace the group with a new version
    x = await aclient.patch(
        f"/cm-service/v2/nodes/{group.id}",
        headers={"Content-Type": "application/json-patch+json"},
        json=[
            {
                "op": "add",
                "path": "/configuration/butler/predicates/-",
                "value": "exposure != 1324567890",
            },
        ],
    )
    assert x.is_success
    new_group = x.json()
    x = await aclient.put(
        f"/cm-service/v2/campaigns/{campaign_id}/graph/nodes/{group.id}?with-node={new_group['id']}",
    )
    assert x.is_success

    # Prepare the new group node
    s = (
        select(Node)
        .where(Node.name == "lambert_group_001")
        .where(Node.namespace == campaign_id)
        .where(Node.version == 2)
        .options(selectinload(cast(InstrumentedAttribute, Node.fsm)))
    )

    group = (await session.exec(s)).one()
    group_machine = GroupMachine(o=group)
    await group_machine.trigger("prepare")

    # Assert that the new group's artifact path exists and that the previous
    # group's path does not interfere
    group_path = group.metadata_.get("artifact_path")
    assert group_path is not None
    assert Path(group_path).exists()


async def test_group_fail_retry(
    test_campaign_groups: str, session: AsyncSession, aclient: AsyncClient
) -> None:
    """Tests the retry/rollback behavior of a group node after a failure."""
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Fetch and prepare a step
    node_id = uuid5(UUID(campaign_id), "lambert.1")
    node = await session.get_one(Node, node_id)
    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Fetch and prepare a group
    s = (
        select(Node)
        .where(Node.name == "lambert_group_001")
        .where(Node.namespace == campaign_id)
        .where(Node.version == 1)
    )

    group = (await session.exec(s)).one()
    group_machine = GroupMachine(o=group, initial_state=group.status)
    await session.commit()

    await group_machine.trigger("prepare")
    with patch(
        "lsst.cmservice.machines.node.GroupMachine.do_start",
        side_effect=RuntimeError("Error: unknown error"),
    ):
        await group_machine.trigger("start")

    await session.refresh(group, ["status", "metadata_", "machine"])

    # assert node failed
    x = await aclient.get(f"/cm-service/v2/nodes/{group.id}")
    assert x.is_success
    assert x.json()["status"] == "failed"

    # - trigger 'retry' by setting the status to ready
    x = await aclient.patch(
        f"/cm-service/v2/nodes/{group.id}",
        json={"status": "ready"},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert x.is_success
    await session.refresh(group, ["status", "metadata_", "machine"])
    group_status = group.status
    assert group_status is StatusEnum.ready
    assert group.metadata_["retries"] == 1

    group_machine_pickle = await session.get_one(Machine, group.machine)
    group_machine = (pickle.loads(group_machine_pickle.state)).model
    group_machine.db_model = group

    with patch(
        "lsst.cmservice.machines.node.GroupMachine.do_start",
        return_value=True,
    ):
        await group_machine.trigger("start")

    await session.refresh(group, ["status"])
    group_status = group.status
    assert group_status is StatusEnum.running

    group_artifact_path = group.metadata_.get("artifact_path")
    assert group_artifact_path is not None

    # Cause the running group to fail
    with patch(
        "lsst.cmservice.machines.node.GroupMachine.is_done_running",
        side_effect=RuntimeError("Error: unknown error"),
    ):
        await group_machine.trigger("finish")

    # The artifact path should exist
    assert Path(group_artifact_path).exists()

    await session.refresh(group, ["status"])
    group_status = group.status
    assert group_status is StatusEnum.failed

    # trigger 'reset' by setting the status to waiting with force set
    x = await aclient.patch(
        f"/cm-service/v2/nodes/{group.id}",
        json={"status": "waiting"},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert x.is_success

    # wait for and assert background task is successful
    for i in range(5):
        x = await aclient.get(
            x.headers["StatusUpdate"],
        )
        result = x.json()
        if len(result):
            assert not result[0]["detail"]
            break
        else:
            await sleep(1.0)

    await session.refresh(group, ["status", "metadata_"])
    group_status = group.status
    assert group_status is StatusEnum.waiting

    # The artifact path should not exist
    assert not Path(group_artifact_path).exists()


@pytest.mark.parametrize(
    "restartable,expected_detail",
    [
        (False, "not eligible for restart"),
        (True, ""),
    ],
)
async def test_group_restart(
    *,
    restartable: bool,
    expected_detail: str,
    test_campaign_groups: str,
    session: AsyncSession,
    aclient: AsyncClient,
) -> None:
    """Tests the restart behavior of a group node after a failure.

    Tests both the "not restartable" and "restartable" cases for a group.
    """
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Fetch and prepare a step
    node_id = uuid5(UUID(campaign_id), "lambert.1")
    node = await session.get_one(Node, node_id)
    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Fetch and prepare a group
    s = (
        select(Node)
        .where(Node.name == "lambert_group_001")
        .where(Node.namespace == campaign_id)
        .where(Node.version == 1)
    )

    group = (await session.exec(s)).one()
    group_machine = GroupMachine(o=group, initial_state=group.status)
    await session.commit()

    # Prepare and start the group
    await group_machine.trigger("prepare")
    with patch(
        "lsst.cmservice.machines.node.GroupMachine.do_start",
        return_value=True,
    ):
        await group_machine.trigger("start")

    await session.refresh(group, ["status"])
    await session.commit()
    group_status = group.status
    assert group_status is StatusEnum.running

    group_artifact_path = group.metadata_.get("artifact_path")
    assert group_artifact_path is not None

    # Create mock BPS runtime artifacts
    mock_bps_submit_path = Path(group_artifact_path) / "submit" / "20251111T111100Z"
    mock_bps_submit_path.mkdir(parents=True, exist_ok=False)
    mock_bps_run_name = "u_cmservice_test_group_restart_lambert_001_version_1"

    # Mock BPS stdout log
    p = Path(group_artifact_path) / group_machine.configuration_chain["bps"]["stdout_log"]
    p.write_text(
        dedent(f"""\
        Submit dir: {mock_bps_submit_path}
        Run Id: 27169228.0
        Run Name: {mock_bps_run_name}
        """)
    )

    # Mock BPS QG file
    if restartable:
        p = (mock_bps_submit_path / mock_bps_run_name).with_suffix(".qg")
        p.touch()

    with (
        patch(
            "lsst.cmservice.machines.nodes.group.NodeMachine.is_done_running",
            return_value=True,
        ) as mock_a,
        patch(
            "lsst.cmservice.machines.nodes.group.GroupMachine.check_bps_report",
            side_effect=RuntimeError("WMS Job is Failed"),
        ) as mock_b,
    ):
        await group_machine.trigger("finish")
        assert mock_a.called
        assert mock_b.called

    await session.refresh(group, ["status"])
    group_status = group.status
    assert group_status is StatusEnum.failed

    # trigger 'restart' by setting the status to ready
    x = await aclient.patch(
        f"/cm-service/v2/nodes/{group.id}",
        json={"status": "ready", "force": "true"},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert x.is_success

    # wait for and assert background task is successful
    update_url = x.headers["StatusUpdate"]
    for i in range(5):
        x = await aclient.get(update_url)
        result = x.json()
        if len(result):
            if not (detail := result[0]["detail"]):
                assert not detail
            else:
                assert expected_detail in detail["error"]
                return
            break
        else:
            await sleep(1.0)

    await session.refresh(group, ["status", "metadata_"])
    group_status = group.status
    assert group_status is StatusEnum.ready
    assert group.metadata_["restarts"] == 1

    # assert new and changed artifacts
    assert (Path(group_artifact_path) / "lambert_group_001_restart.sh").exists()
    assert (Path(group_artifact_path) / "lambert_group_001.sub").exists()

    # make sure the new restart script is the payload for the htcondor sub file
    lines = (Path(group_artifact_path) / "lambert_group_001.sub").read_text().splitlines()
    assert f"""executable = {Path(group_artifact_path) / "lambert_group_001_restart.sh"}""" in lines

    await session.refresh(group, ["status"])
    group_status = group.status
    assert group_status is StatusEnum.ready


@pytest.mark.parametrize(
    "acceptable,expected_status",
    [
        (True, StatusEnum.accepted),
        (False, StatusEnum.failed),
    ],
)
async def test_group_force_accept(
    *,
    acceptable: bool,
    expected_status: StatusEnum,
    test_campaign_groups: str,
    session: AsyncSession,
    aclient: AsyncClient,
) -> None:
    """Tests the unconditional acceptance of a failed group."""
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Fetch and prepare a step
    node_id = uuid5(UUID(campaign_id), "lambert.1")
    node = await session.get_one(Node, node_id)
    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Fetch and prepare a group
    s = (
        select(Node)
        .where(Node.name == "lambert_group_001")
        .where(Node.namespace == campaign_id)
        .where(Node.version == 1)
    )

    group = (await session.exec(s)).one()
    group_machine = GroupMachine(o=group, initial_state=group.status)
    await session.commit()

    await group_machine.trigger("prepare")
    with patch(
        "lsst.cmservice.machines.node.GroupMachine.do_start",
        side_effect=RuntimeError("Error: unknown error"),
    ):
        await group_machine.trigger("start")

    await session.refresh(group, ["status", "metadata_", "machine"])

    # assert node failed
    x = await aclient.get(f"/cm-service/v2/nodes/{group.id}")
    assert x.is_success
    assert x.json()["status"] == "failed"

    # - trigger 'force' by setting the status to accepted
    x = await aclient.patch(
        f"/cm-service/v2/nodes/{group.id}",
        json={"status": "accepted", "force": acceptable},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert x.is_success
    await session.refresh(group, ["status", "metadata_", "machine"])
    group_status = group.status
    assert group_status is expected_status


async def test_step_fail_reset(
    *,
    test_campaign_groups: str,
    session: AsyncSession,
    aclient: AsyncClient,
) -> None:
    """Tests that a failed Step is recoverable with the reset trigger"""
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Fetch and FAIL to prepare a step, as a broken manifest may cause
    step_id = uuid5(UUID(campaign_id), "lambert.1")
    step = await session.get_one(Node, step_id)
    step_machine = StepMachine(o=step)
    with patch(
        "lsst.cmservice.machines.node.StepMachine.do_prepare",
        side_effect=RuntimeError("Step failed to prepare"),
    ):
        await step_machine.trigger("prepare")

    await session.refresh(step, ["status"])
    await session.commit()
    step_status = step.status
    assert step_status is StatusEnum.failed

    # trigger 'RESET' by setting the status to waiting
    x = await aclient.patch(
        f"/cm-service/v2/nodes/{step.id}",
        json={"status": "waiting", "force": "true"},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert x.is_success

    # wait for and assert background task is successful
    update_url = x.headers["StatusUpdate"]
    for _ in range(5):
        x = await aclient.get(update_url)
        result = x.json()
        if len(result):
            activity_log_message = result[0]["detail"]["message"]
            assert "rolled back" in activity_log_message
            break
        else:
            await sleep(1.0)

    await session.refresh(step, ["status", "metadata_"])
    step_status = step.status
    assert step_status is StatusEnum.waiting
