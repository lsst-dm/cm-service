"""Tests v2 fastapi edge routes"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_list_delete_no_edges(aclient: AsyncClient) -> None:
    """Tests listing and deleting edges when there are no edges available."""
    x = await aclient.get("/cm-service/v2/edges")
    assert x.is_success
    assert len(x.json()) == 0

    x = await aclient.get(f"/cm-service/v2/edges/{uuid4()}")
    assert x.status_code == 404

    x = await aclient.delete(f"/cm-service/v2/edges/{uuid4()}")
    assert x.status_code == 404


async def test_edge_negative(aclient: AsyncClient) -> None:
    """Tests edge route negative outcomes."""

    # negative test: failing request model validation
    x = await aclient.post(
        "cm-service/v2/edges",
        json={
            "kind": "no_such_kind",
        },
    )
    assert x.is_client_error

    # negative test: using wrong manifest kind
    x = await aclient.post(
        "cm-service/v2/edges",
        json={
            "kind": "other",
        },
    )
    assert x.is_client_error

    # negative test: missing edge source or target
    x = await aclient.post(
        "cm-service/v2/edges",
        json={
            "kind": "edge",
            "metadata": {"name": uuid4().hex[8:], "namespace": "test_campaign"},
            "spec": {
                "source": "START",
            },
        },
    )
    assert x.is_client_error

    x = await aclient.post(
        "cm-service/v2/edges",
        json={
            "kind": "edge",
            "metadata": {"name": uuid4().hex[8:], "namespace": "test_campaign"},
            "spec": {
                "target": "END",
            },
        },
    )
    assert x.is_client_error

    # negative test: missing campaign namespace
    x = await aclient.post(
        "cm-service/v2/edges",
        json={
            "kind": "edge",
            "metadata": {"name": uuid4().hex[8:]},
            "spec": {"source": "START", "target": "END"},
        },
    )
    assert x.is_client_error

    # negative: fail to delete an edge using a non-uuid string (like a name)
    x = await aclient.delete(
        "/cm-service/v2/edges/not_an_edge_id",
    )
    assert x.status_code == 422


async def test_edge_lifecycle(aclient: AsyncClient) -> None:
    """Tests edge lifecycle."""
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

    # Create an edge between START and END
    x = await aclient.post(
        "/cm-service/v2/edges",
        json={
            "kind": "edge",
            "metadata": {
                "name": uuid4().hex[8:],
                "namespace": campaign_id,
            },
            "spec": {
                "source": "START",
                "target": "END",
            },
        },
    )
    assert x.is_success
    assert "Campaign" in x.headers
    edge = x.json()
    edge_name = edge["name"]
    edge_self_url = x.headers["Self"]
    target_node_url = x.headers["Target"]
    source_node_url = x.headers["Source"]

    # Verify header links to source and target nodes
    x = await aclient.get(source_node_url)
    assert x.is_success
    assert x.json()["name"] == "START"

    x = await aclient.get(target_node_url)
    assert x.is_success
    assert x.json()["name"] == "END"

    x = await aclient.get(f"/cm-service/v2/edges/{edge_name}")
    assert x.is_success
    edge = x.json()

    x = await aclient.delete(f"{edge_self_url}")
    assert x.is_success
