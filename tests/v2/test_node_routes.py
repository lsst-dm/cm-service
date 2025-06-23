"""Tests v2 fastapi node routes"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_list_delete_no_nodes(aclient: AsyncClient) -> None:
    """Tests listing nodes when there are no nodes available."""
    x = await aclient.get("/cm-service/v2/nodes")
    assert x.is_success
    assert len(x.json()) == 0

    x = await aclient.get(f"/cm-service/v2/nodes/{uuid4()}")
    assert x.status_code == 404

    # there is no delete api for nodes
    x = await aclient.delete(f"/cm-service/v2/nodes/{uuid4()}")
    assert x.status_code == 405


async def test_node_negative(aclient: AsyncClient) -> None:
    """Tests node route negative outcomes."""

    # negative test: failing request model validation
    x = await aclient.post(
        "cm-service/v2/nodes",
        json={
            "kind": "no_such_kind",
        },
    )
    assert x.is_client_error

    # negative test: using wrong manifest kind
    x = await aclient.post(
        "cm-service/v2/nodes",
        json={
            "kind": "other",
        },
    )
    assert x.is_client_error

    # negative test: missing node name
    x = await aclient.post(
        "cm-service/v2/nodes",
        json={
            "kind": "node",
            "metadata": {},
            "spec": {},
        },
    )
    assert x.is_client_error

    # negative test: missing campaign namespace
    x = await aclient.post(
        "cm-service/v2/nodes",
        json={
            "kind": "node",
            "metadata": {"name": uuid4().hex[8:]},
            "spec": {},
        },
    )
    assert x.is_client_error


async def test_node_lifecycle(aclient: AsyncClient) -> None:
    """Tests node lifecycle."""
    campaign_name = uuid4().hex[:8]

    # Create a campaign for edges. Campaigns come with START and END nodes.
    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "kind": "campaign",
            "metadata": {"name": campaign_name},
            "spec": {},
        },
    )
    assert x.is_success
    campaign_id = x.json()["id"]

    # Create a new campaign node
    x = await aclient.post(
        "/cm-service/v2/nodes",
        json={
            "kind": "node",
            "metadata": {"name": uuid4().hex[8:], "namespace": campaign_id},
            "spec": {
                "handler": "lsst.cmservice.handlers.element_handler.ElementHandler",
                "pipeline_yaml": "${DRP_PIPE_DIR}/pipelines/HSC/DRP-RC2.yaml#step1",
                "query": [{"instrument": "HSC"}, {"skymap": "hsc_rings_v1"}],
                "split": {
                    "dataset": "raw",
                    "field": "exposure",
                    "method": "query",
                    "minGroups": 3,
                    "maxInFlight": 3,
                },
            },
        },
    )
    assert x.is_success
    node = x.json()
    assert node["version"] == 1
    node_url = x.headers["Self"]

    # Edit a Node using RFC6902 json-patch
    x = await aclient.patch(
        node_url,
        headers={"Content-Type": "application/json-patch+json"},
        json=[
            {"op": "replace", "path": "/configuration/split/maxInFlight", "value": 4},
            {
                "op": "add",
                "path": "/configuration/query/-",
                "value": {"dimension": "fact"},
            },
        ],
    )
    assert x.is_success
    node = x.json()

    # test that the updates have been made and the version has been bumped
    assert node["configuration"]["split"]["maxInFlight"] == 4
    assert node["configuration"]["query"][-1]["dimension"] == "fact"
    assert node["version"] == 2
