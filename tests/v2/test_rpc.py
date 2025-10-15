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
