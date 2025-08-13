"""Tests v2 fastapi campaign routes"""

from uuid import NAMESPACE_DNS, uuid4, uuid5

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_list_campaigns(aclient: AsyncClient) -> None:
    """Tests listing the set of all campaigns."""
    # initially, only the default campaign should be available, which is hidden
    # from view via this api
    x = await aclient.get("/cm-service/v2/campaigns")
    assert len(x.json()) == 0

    x = await aclient.get("/cm-service/v2/campaigns", headers={"CM-Admin-View": "true"})
    assert len(x.json()) == 1


async def test_list_campaign(aclient: AsyncClient) -> None:
    """Tests lookup of a single campaign by name and by ID"""
    campaign_name = uuid4().hex[-8:]

    x = await aclient.get(
        f"/cm-service/v2/campaigns/{campaign_name}",
    )
    assert x.status_code == 404

    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "campaign",
            "metadata_": {"name": campaign_name},
            "spec": {},
        },
    )
    assert x.is_success
    campaign_id = x.json()["id"]

    x = await aclient.get(
        f"/cm-service/v2/campaigns/{campaign_name}",
    )
    assert x.is_success

    x = await aclient.get(
        f"/cm-service/v2/campaigns/{campaign_id}",
    )
    assert x.is_success


async def test_negative_campaign(aclient: AsyncClient) -> None:
    """Tests campaign api negative results."""
    # Test failure to create campaign with invalid manifest (wrong kind)
    campaign_name = uuid4().hex[-8:]

    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "node",
            "metadata": {
                "name": campaign_name,
            },
            "spec": {},
        },
    )
    assert x.is_client_error

    # Test failure to create campaign with incomplete manifest (missing name)
    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "campaign",
            "metadata": {},
            "spec": {},
        },
    )
    assert x.is_client_error


async def test_create_campaign(aclient: AsyncClient) -> None:
    """Tests the campaign creation API"""
    campaign_name = uuid4().hex[-8:]

    # Test successful campaign creation
    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "campaign",
            "metadata": {"name": campaign_name},
            "spec": {},
        },
    )
    assert x.is_success

    campaign = x.json()
    # - the campaign should exist in the namespace of the default campaign
    assert campaign["namespace"] == str(uuid5(NAMESPACE_DNS, "io.lsst.cmservice"))
    # - the returned campaign's ID should be the name of the campaign within
    #   the namespace of the default campaign
    assert campaign["id"] == str(uuid5(uuid5(NAMESPACE_DNS, "io.lsst.cmservice"), campaign_name))
    assert campaign["status"] == "waiting"

    # - the response headers should have pointers to other API endpoints for
    #   the campaign
    assert set(["self", "nodes", "edges"]) <= x.headers.keys()

    # - the provided links should be valid
    y = await aclient.get(x.headers["self"])
    assert y.is_success

    y = await aclient.get(x.headers["nodes"])
    assert y.is_success
    # A new empty campaign should have a START and END node
    nodes = y.json()
    assert len(nodes) == 2
    y = await aclient.get(x.headers["edges"])
    assert y.is_success
    # A new empty campaign should not have any edges
    edges = y.json()
    assert len(edges) == 0


async def test_patch_campaign(aclient: AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    """Tests the campaign update API"""
    # Create a new campaign with spec data
    campaign_name = uuid4().hex[-8:]
    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "campaign",
            "metadata_": {"name": campaign_name},
            "spec": {
                "collections": ["a", "b", "c"],
                "enable_notifications": True,
            },
        },
    )

    assert x.is_success
    # The response header 'self' has the canonical url for the new campaign
    campaign_url = x.headers["self"]

    # Try an unsupported content-type for patch
    y = await aclient.patch(
        campaign_url,
        json={"status": "ready", "owner": "bob_loblaw"},
        headers={"Content-Type": "application/not-supported+json"},
    )
    assert y.status_code == 406

    # Update the campaign using RFC6902
    y = await aclient.patch(
        campaign_url,
        json={"status": "ready", "owner": "bob_loblaw"},
        headers={"Content-Type": "application/json-patch+json"},
    )
    # RFC6902 not implemented
    assert y.status_code == 501

    # Update the campaign using RFC7396 and campaign id
    caplog.clear()
    y = await aclient.patch(
        campaign_url,
        json={"status": "running", "owner": "bob_loblaw"},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert y.is_success
    # Obtain the Status Update URL from the response headers
    status_update_url = y.headers["StatusUpdate"]

    # Check the updates are as expected
    updated_campaign = y.json()
    assert updated_campaign["owner"] == "bob_loblaw"
    # the status update will not be applied
    assert updated_campaign["status"] == "waiting"

    # we should see a failed transition in the log
    log_entry_found = False
    for r in caplog.records:
        if "InvalidCampaignGraphError" in r.message:
            log_entry_found = True
            break
    assert log_entry_found

    # Update the campaign again using RFC7396, ensuring only a single field
    # is patched, using campaign name
    y = await aclient.patch(
        f"/cm-service/v2/campaigns/{campaign_name}",
        json={"owner": "alice_bob"},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    assert y.is_success
    updated_campaign = y.json()
    assert updated_campaign["owner"] == "alice_bob"
    # the previous status update will not be successful
    assert updated_campaign["status"] == "waiting"

    # The (failed) attempt to resume a campaign with a broken graph should
    # produce an error detail at the reported location, i.e., at the logs
    # API with a request-id query param.
    y = await aclient.get(status_update_url)
    assert y.is_success
    activity_log_entry = y.json()[0]
    assert activity_log_entry["detail"]["trigger"] == "start"
    assert activity_log_entry["detail"]["exception"] == "InvalidCampaignGraphError"
