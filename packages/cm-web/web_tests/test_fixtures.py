"""Smoke tests for the cm-web test fixtures."""

from datetime import UTC, datetime

import pytest
from httpx import Response, codes
from nicegui.testing.user import User
from respx.models import AllMockedAssertionError

from lsst.cmservice.models.enums import DEFAULT_NAMESPACE
from lsst.cmservice.web import api
from lsst.cmservice.web.lib.client_factory import ClientFactory

from .conftest import FakeCMService


async def test_overview_page_without_campaigns(user: User) -> None:
    await user.open("/")
    await user.should_see("Campaign Overview")


async def test_overview_page_with_campaign(user: User, cm_api: FakeCMService) -> None:
    cm_api.add_campaign("nostromo", nodes=["ripley", "dallas"], status="running")
    await user.open("/")
    await user.should_see("nostromo")
    assert cm_api.router.routes["campaign_summary"].call_count == 1


async def test_describe_one_campaign(cm_api: FakeCMService, client_factory: ClientFactory) -> None:
    campaign = cm_api.add_campaign("sulaco", nodes=["hicks", "hudson", "vasquez"])
    async with client_factory.aclient() as aclient:
        detail = await api.describe_one_campaign(campaign["id"], aclient)

    assert detail["campaign"]["name"] == "sulaco"
    assert {n["name"] for n in detail["nodes"]} == {"START", "hicks", "hudson", "vasquez", "END"}
    assert len(detail["graph"]["edges"]) == 4
    assert detail["manifests"] == []


async def test_get_default_library_manifest(cm_api: FakeCMService) -> None:
    namespace = str(DEFAULT_NAMESPACE)
    assert await api.get_one_manifest(namespace=namespace, kind="lsst", default=True) is None

    cm_api.add_manifest(
        "lsst",
        "w_latest",
        spec={"lsst_version": "w_latest", "lsst_distrib_dir": "/path/to/lsst/distrib/w_latest"},
        default=True,
    )
    r = await api.get_one_manifest(namespace=namespace, kind="lsst", default=True)
    assert r is not None
    assert r.json()["name"] == "w_latest"

    manifests = await api.get_campaign_manifests()
    assert [m["kind"] for m in manifests] == ["lsst"]


async def test_writes_must_be_mocked(cm_api: FakeCMService) -> None:
    campaign = cm_api.add_campaign("narcissus", configuration={"notification_labels": ["mother"]})

    with pytest.raises(AllMockedAssertionError):
        await api.apply_notification_labels(campaign)

    patch_route = cm_api.router.patch(f"/campaigns/{campaign['id']}").respond(codes.OK, json=campaign)
    await api.apply_notification_labels(campaign)
    assert patch_route.called
    assert patch_route.calls.last.request.headers["Content-Type"] == "application/merge-patch+json"


async def test_route_override(cm_api: FakeCMService, client_factory: ClientFactory) -> None:
    cm_api.router.routes["campaigns"].mock(return_value=Response(codes.INTERNAL_SERVER_ERROR))
    async with client_factory.aclient() as aclient:
        r = await aclient.get("/campaigns/")
    assert r.status_code == codes.INTERNAL_SERVER_ERROR


async def test_activity_log_collection(cm_api: FakeCMService, client_factory: ClientFactory) -> None:
    """The fake activity log collection is filtered, sorted, and paginated
    like the API's.
    """
    campaign = cm_api.add_campaign("prometheus", nodes=["shaw", "holloway"])
    shaw, holloway = (n for n in cm_api.nodes.values() if n["name"] in ("shaw", "holloway"))
    for minute, node, to_status in ((1, shaw, "ready"), (2, holloway, "ready"), (3, shaw, "running")):
        cm_api.add_log(
            campaign["id"],
            node_id=node["id"],
            from_status="waiting" if to_status == "ready" else "ready",
            to_status=to_status,
            finished_at=datetime(2026, 11, 1, 12, minute, tzinfo=UTC),
        )

    async with client_factory.aclient() as aclient:
        r = await aclient.get(f"/logs/?node={shaw['id']}&sort=-finished_at")
        assert [log["to_status"] for log in r.json()] == ["running", "ready"]

        r = await aclient.get(f"/logs/?campaign={campaign['id']}")
        assert [log["finished_at"][11:16] for log in r.json()] == ["12:01", "12:02", "12:03"]

        r = await aclient.get(f"/logs/?campaign={campaign['id']}&sort=-finished_at&limit=2&offset=1")
        assert [log["finished_at"][11:16] for log in r.json()] == ["12:02", "12:01"]
