"""Tests v2 fastapi rpc routes"""

from unittest.mock import Mock, patch
from urllib.parse import urlparse
from uuid import UUID, uuid5

import pytest
from httpx import AsyncClient, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.common.daemon_v2 import consider_nodes
from lsst.cmservice.common.launchers import LauncherCheckResponse
from lsst.cmservice.db.campaigns_v2 import Task

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
    session: AsyncSession,
) -> None:
    """Tests the manual step-through of a campaign node using the "process" RPC
    API.
    """
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "START.1")

    async def process_once() -> Response:
        r = await aclient.post(
            "/cm-service/v2/rpc/process",
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
    await consider_nodes(session)
    found_log_messages = 0
    for r in caplog.records:
        if any(["evolving node" in r.message]):
            found_log_messages += 1
    assert found_log_messages == 1

    # A task should now be in the task table
    tasks = (await session.exec(select(Task))).all()
    assert len(tasks) == 1

    # The node should now be in the "ready" state
    x = await aclient.get(f"/cm-service/v2/nodes/{node_id}")
    assert x.is_success
    assert x.json()["status"] == "ready"

    # Use the RPC API to process the node into a "running" state
    x = await process_once()
    assert x.is_success
    await consider_nodes(session)

    x = await aclient.get(f"/cm-service/v2/nodes/{node_id}")
    assert x.is_success
    assert x.json()["status"] == "running"

    # Use the RPC API to process the node into a "accepted" state
    x = await process_once()
    assert x.is_success
    await consider_nodes(session)

    x = await aclient.get(f"/cm-service/v2/nodes/{node_id}")
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
            "/cm-service/v2/rpc/process",
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
    session: AsyncSession,
) -> None:
    """Tests the addition of a Breakpoint node in a campaign, and that process-
    ing the campaign does not proceed past the breakpoint until it is applied
    the "force" transition.
    """
    campaign_id = urlparse(url=test_campaign).path.split("/")[-2:][0]
    start_id = uuid5(UUID(campaign_id), "START.1")

    async def process_once() -> Response:
        r = await aclient.post(
            "/cm-service/v2/rpc/process",
            json={
                "campaign_id": campaign_id,
            },
        )
        return r

    # Add a breakpoint node after the START node
    # create a new Node in the campaign
    r = await aclient.post(
        "/cm-service/v2/nodes",
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
        f"/cm-service/v2/campaigns/{campaign_id}/graph/nodes/{start_id}?add-node={breakpoint_id}&operation=insert",
    )
    assert r.is_success

    # use RPC to process the campaign until the breakpoint node is running
    # FIXME if there are timing issues here, we can introduce sleeps or try to
    # use wait-for-activity-log logic assuming request_ids are working
    for _ in range(5):
        x = await process_once()
        assert x.is_success
        await consider_nodes(session)

    # confirm that the breakpoint node does not advance from "running"
    r = await aclient.get(breakpoint_url)
    assert r.json()["status"] == "running"

    x = await process_once()
    assert x.is_success
    await consider_nodes(session)

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
    await consider_nodes(session)
