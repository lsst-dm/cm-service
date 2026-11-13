"""Tests v2 fastapi rpc routes"""

from unittest.mock import Mock, patch
from urllib.parse import urlparse
from uuid import UUID, uuid5

import pytest
from httpx2 import AsyncClient, Response
from sqlmodel import select

from lsst.cmservice.common.daemon_v2 import DaemonContext, consider_nodes
from lsst.cmservice.common.launchers import LauncherCheckResponse
from lsst.cmservice.models.db.campaigns import Task

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


@patch("lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.launch", return_value=None)
@patch(
    "lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.check",
    return_value=LauncherCheckResponse(success=True),
)
async def test_rpc_process_node(
    mock_check: Mock,
    mock_launch: Mock,
    caplog: pytest.LogCaptureFixture,
    test_campaign: str,
    aclient: AsyncClient,
    daemon_context: DaemonContext,
) -> None:
    """Tests the manual step-through of a campaign node using the "process" RPC
    API.
    """
    session = daemon_context.session
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "START.1")

    async def process_once() -> Response:
        r = await aclient.post(
            "/v2/rpc/process",
            json={
                "node_id": str(node_id),
                "campaign_id": campaign_id,
            },
        )
        return r

    x = await process_once()
    assert x.is_success

    # now the daemon should consider the prepared campaign
    caplog.clear()
    await consider_nodes(daemon_context)
    found_log_messages = 0
    for r in caplog.records:
        if any(["evolving node" in r.message]):
            found_log_messages += 1
    assert found_log_messages == 1

    # A task should now be in the task table
    tasks = (await session.exec(select(Task))).all()
    assert len(tasks) == 1

    # The node should now be in the "ready" state
    x = await aclient.get(f"/v2/nodes/{node_id}")
    assert x.is_success
    assert x.json()["status"] == "ready"

    # Use the RPC API to process the node into a "running" state
    x = await process_once()
    assert x.is_success
    await consider_nodes(daemon_context)

    x = await aclient.get(f"/v2/nodes/{node_id}")
    assert x.is_success
    assert x.json()["status"] == "running"

    # Use the RPC API to process the node into a "accepted" state
    x = await process_once()
    assert x.is_success
    await consider_nodes(daemon_context)

    x = await aclient.get(f"/v2/nodes/{node_id}")
    assert x.is_success
    assert x.json()["status"] == "accepted"


async def test_rpc_process_wrong_node(
    test_campaign: str,
    aclient: AsyncClient,
) -> None:
    """Tests the manual step-through of a campaign node using the "process" RPC
    API.
    """
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "END.1")

    async def process_once() -> Response:
        r = await aclient.post(
            "/v2/rpc/process",
            json={
                "node_id": str(node_id),
                "campaign_id": campaign_id,
            },
        )
        return r

    x = await process_once()
    assert not x.is_success
    assert x.status_code == 422
    assert "not processable" in x.text


@patch("lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.launch", return_value=None)
@patch(
    "lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.check",
    return_value=LauncherCheckResponse(success=True),
)
async def test_rpc_with_breakpoint_node(
    mock_check: Mock,
    mock_launch: Mock,
    test_campaign: str,
    aclient: AsyncClient,
    daemon_context: DaemonContext,
) -> None:
    """Tests the addition of a Breakpoint node in a campaign, and that process-
    ing the campaign does not proceed past the breakpoint until it is applied
    the "force" transition.
    """
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    start_id = uuid5(UUID(campaign_id), "START.1")

    async def process_once() -> Response:
        r = await aclient.post(
            "/v2/rpc/process",
            json={
                "campaign_id": campaign_id,
            },
        )
        return r

    # Add a breakpoint node after the START node
    # create a new Node in the campaign
    r = await aclient.post(
        "/v2/nodes",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "node",
            "metadata": {"name": "holdup", "namespace": campaign_id, "kind": "breakpoint"},
            "spec": {},
        },
    )
    assert r.is_success
    breakpoint_id = r.json()["id"]
    breakpoint_url = r.headers["self"]

    # INSERT the new node in the campaign downstream of Start
    r = await aclient.patch(
        f"/v2/campaigns/{campaign_id}/graph/nodes/{start_id}?add-node={breakpoint_id}&operation=insert",
    )
    assert r.is_success

    # use RPC to process the campaign until the breakpoint node is running
    # FIXME if there are timing issues here, we can introduce sleeps or try to
    # use wait-for-activity-log logic assuming request_ids are working
    for _ in range(5):
        x = await process_once()
        assert x.is_success
        await consider_nodes(daemon_context)

    # confirm that the breakpoint node does not advance from "running"
    r = await aclient.get(breakpoint_url)
    assert r.json()["status"] == "running"

    x = await process_once()
    assert x.is_success
    await consider_nodes(daemon_context)

    r = await aclient.get(breakpoint_url)
    assert r.json()["status"] == "running"

    # manually force the breakpoint node
    # - trigger 'force' by setting the status to accepted
    x = await aclient.patch(
        breakpoint_url,
        json={"status": "accepted", "force": True},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert x.is_success

    r = await aclient.get(breakpoint_url)
    assert r.json()["status"] == "accepted"

    # confirm that the rpc proceeds to the next node
    x = await process_once()
    assert x.is_success
    await consider_nodes(daemon_context)


@pytest.mark.parametrize("reject_from", ["waiting", "running", "accepted"])
@patch("lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.launch", return_value=None)
@patch(
    "lsst.cmservice.machines.nodes.mixin.HTCondorLaunchMixin.check",
    return_value=LauncherCheckResponse(success=True),
)
async def test_rpc_reject_breakpoint_node(
    mock_check: Mock,
    mock_launch: Mock,
    *,
    reject_from: str,
    test_campaign: str,
    aclient: AsyncClient,
    daemon_context: DaemonContext,
) -> None:
    """Tests that rejecting a Breakpoint node, whether before the campaign
    reaches it, while it holds the campaign, or after it is accepted, puts it
    in the rejected state and produces the activity log entry for which a
    requester waits. A second rejection is refused and the refusal recorded.
    """
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    start_id = uuid5(UUID(campaign_id), "START.1")

    async def process_once() -> None:
        r = await aclient.post("/v2/rpc/process", json={"campaign_id": campaign_id})
        assert r.is_success
        await consider_nodes(daemon_context)

    async def patch_status(url: str, status: str) -> list[dict]:
        """PATCH a node status and return the activity log entries for the
        request.
        """
        r = await aclient.patch(
            url,
            json={"status": status, "force": True},
            headers={"Content-Type": "application/merge-patch+json"},
        )
        assert r.is_success
        activity = await aclient.get(r.headers["StatusUpdate"])
        assert activity.is_success
        return activity.json()

    async def get_status(url: str) -> str:
        return (await aclient.get(url)).json()["status"]

    # Insert a breakpoint node downstream of START
    r = await aclient.post(
        "/v2/nodes",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "node",
            "metadata": {"name": "holdup", "namespace": campaign_id, "kind": "breakpoint"},
            "spec": {},
        },
    )
    assert r.is_success
    breakpoint_id = r.json()["id"]
    breakpoint_url = r.headers["self"]

    r = await aclient.patch(
        f"/v2/campaigns/{campaign_id}/graph/nodes/{start_id}?add-node={breakpoint_id}&operation=insert",
    )
    assert r.is_success

    if reject_from != "waiting":
        # Process the campaign until the breakpoint node is running
        for _ in range(5):
            await process_once()
        assert await get_status(breakpoint_url) == "running"

    if reject_from == "accepted":
        await patch_status(breakpoint_url, "accepted")

    assert await get_status(breakpoint_url) == reject_from

    # Reject the breakpoint
    activity = await patch_status(breakpoint_url, "rejected")
    assert await get_status(breakpoint_url) == "rejected"
    assert activity
    assert activity[0]["to_status"] == "rejected"
    assert "error" not in activity[0]["detail"]

    # A rejected breakpoint cannot be rejected again
    activity = await patch_status(breakpoint_url, "rejected")
    assert await get_status(breakpoint_url) == "rejected"
    assert len(activity) == 1
    assert "error" in activity[0]["detail"]

    # The campaign does not proceed past the rejected breakpoint
    edges = (await aclient.get(test_campaign)).json()
    successor_urls = [f"/v2/nodes/{e['target']}" for e in edges if e["source"] == breakpoint_id]
    assert successor_urls
    for _ in range(3):
        await process_once()
    for url in successor_urls:
        assert await get_status(url) == "waiting"

    # Until the pilot accepts the breakpoint
    await patch_status(breakpoint_url, "accepted")
    assert await get_status(breakpoint_url) == "accepted"
    await process_once()
    for url in successor_urls:
        assert await get_status(url) != "waiting"


async def test_refused_node_transition_is_recorded(test_campaign: str, aclient: AsyncClient) -> None:
    """Tests that a requested node state change that cannot be performed
    produces an activity log entry describing the refusal, rather than failing
    silently.
    """
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    start_id = uuid5(UUID(campaign_id), "START.1")

    # There is no transition from waiting to rejected for an ordinary node
    r = await aclient.patch(
        f"/v2/nodes/{start_id}",
        json={"status": "rejected", "force": True},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert r.is_success
    activity = (await aclient.get(r.headers["StatusUpdate"])).json()
    assert len(activity) == 1
    assert activity[0]["to_status"] == "waiting"
    assert "cannot be changed from waiting to rejected" in activity[0]["detail"]["error"]

    r = await aclient.get(f"/v2/nodes/{start_id}")
    assert r.json()["status"] == "waiting"
