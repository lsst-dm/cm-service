"""Tests for schedules with an external resource"""

from textwrap import dedent
from uuid import UUID, uuid4

import pytest
import respx
import yaml
from httpx2 import AsyncClient, codes
from pydantic_extra_types.cron import CronStr

from lsst.cmservice.common.daemon_v2 import daemon_scheduled_job
from lsst.cmservice.common.schedule_resources import (
    ScheduleResourceError,
    apply_schedule_spec,
    fetch_schedule_resource,
)
from lsst.cmservice.common.scheduler import JobEventReturnCode
from lsst.cmservice.models.api.schedules import ScheduleTriggerBinding
from lsst.cmservice.models.db.schedules import Schedule

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""

TEMPLATES = dedent("""\
    ---
    apiVersion: io.lsst.cmservice/v1
    kind: campaign
    metadata:
        name: resource_campaign
    spec: {}
    ---
    apiVersion: io.lsst.cmservice/v1
    kind: butler
    metadata:
        name: resource_butler
        namespace: b67094a8-c44f-50b7-a2db-81c95a16fd29
        version: 0
    spec:
        collections:
            campaign_input:
            - LSSTCam/defaults
        predicates:
            - day_obs=${{ day_obs }}
        repo: /repo/main
""")


def make_resource(schedule_spec: dict | None = None) -> str:
    """Returns the content of an external resource with the test templates
    and, optionally, a schedule manifest with the given spec.
    """
    if schedule_spec is None:
        return TEMPLATES
    schedule_manifest = {
        "apiVersion": "io.lsst.cmservice/v1",
        "kind": "schedule",
        "metadata": {"owner": "root"},
        "spec": schedule_spec,
    }
    return TEMPLATES + yaml.safe_dump(schedule_manifest, explicit_start=True)


def make_uri() -> str:
    return f"http://example.com/{uuid4().hex[:8]}/campaign.yaml"


async def get_schedule(aclient: AsyncClient, schedule_url: str) -> dict:
    x = await aclient.get(schedule_url)
    assert x.status_code == codes.OK
    return x.json()[0]


async def create_schedule(aclient: AsyncClient, uri: str | None = None, **configuration: str) -> str:
    """Creates a schedule, with an external resource if a uri is given, and
    returns its url.
    """
    if uri is not None:
        configuration["uri"] = uri
    x = await aclient.post(
        "/v2/schedules",
        json={"name": f"schedule_{uuid4().hex[:8]}", "cron": "0 0 * * SUN", "configuration": configuration},
    )
    assert x.status_code == codes.CREATED, x.text
    return x.headers["Self"]


async def test_apply_schedule_spec() -> None:
    """Tests that a schedule manifest's spec replaces the configuration and
    cron of a schedule, except for its uri.
    """
    uri = make_uri()
    schedule = Schedule(
        name="schedule",
        cron=CronStr("* * * * *"),
        configuration={"uri": uri, "expressions": {"a": "1"}, "name_format": "%s", "extra": 1},
    )
    triggers = [ScheduleTriggerBinding(source="kafka", channel="a_topic", protocol="@")]
    changes = apply_schedule_spec(
        schedule,
        {
            "cron": "0 12 * * *",
            "expressions": {"b": "2"},
            "uri": "http://example.com/other",
            "triggers": triggers,
        },
    )

    # Only the fields the spec sets are stored, and the cron is not
    assert schedule.configuration == {
        "expressions": {"b": "2"},
        "triggers": [{"source": "kafka", "channel": "a_topic", "protocol": "@"}],
        "uri": uri,
    }
    assert str(schedule.cron) == "0 12 * * *"
    # Fields missing from the old or new configuration change from or to None
    assert changes.keys() == {"cron", "expressions", "name_format", "extra", "triggers"}
    assert changes["extra"] == {"from": 1, "to": None}
    assert changes["name_format"] == {"from": "%s", "to": None}
    assert changes["cron"] == {"from": "* * * * *", "to": "0 12 * * *"}

    # Applying the same spec again changes nothing
    assert (
        apply_schedule_spec(schedule, {"cron": "0 12 * * *", "expressions": {"b": "2"}, "triggers": triggers})
        == {}
    )


@pytest.mark.parametrize(
    "spec",
    [{"cron": "not a cron"}, {"auto_start": "maybe"}, {"expressions": []}, {"is_enabled": True}],
    ids=["invalid cron", "invalid auto_start", "invalid expressions", "schedule field"],
)
async def test_apply_invalid_schedule_spec(spec: dict) -> None:
    """Tests that an invalid schedule manifest spec is rejected without
    changing the schedule.
    """
    schedule = Schedule(name="schedule", cron=CronStr("* * * * *"), configuration={"uri": make_uri()})
    configuration = dict(schedule.configuration)
    with pytest.raises(ScheduleResourceError):
        apply_schedule_spec(schedule, spec)
    assert schedule.configuration == configuration
    assert str(schedule.cron) == "* * * * *"


@pytest.mark.parametrize(
    "status_code,content",
    [
        (codes.NOT_FOUND, ""),
        (codes.OK, "kind: [unclosed"),
        (codes.OK, "- a list\n- of strings\n"),
        (codes.OK, "apiVersion: io.lsst.cmservice/v1\nmetadata: {}\n"),
        (
            codes.OK,
            make_resource({"cron": "0 12 * * *"}) + yaml.safe_dump({"kind": "schedule"}, explicit_start=True),
        ),
    ],
    ids=["not found", "invalid yaml", "not a manifest", "no kind", "two schedule manifests"],
)
async def test_fetch_invalid_schedule_resource(
    httpx2_mock: respx.Router, status_code: int, content: str
) -> None:
    """Tests that a resource that cannot be fetched or parsed is rejected."""
    uri = make_uri()
    httpx2_mock.get(uri).respond(status_code, content=content)
    with pytest.raises(ScheduleResourceError):
        await fetch_schedule_resource(uri)


async def test_fetch_schedule_resource(httpx2_mock: respx.Router) -> None:
    """Tests that a resource's schedule manifest is separated from its
    templates.
    """
    uri = make_uri()
    httpx2_mock.get(uri).respond(codes.OK, content=make_resource({"cron": "0 12 * * *"}))
    resource = await fetch_schedule_resource(uri)
    assert resource.schedule_spec == {"cron": "0 12 * * *"}
    assert [t.kind.name for t in resource.templates] == ["campaign", "butler"]

    httpx2_mock.get(uri).respond(codes.OK, content=make_resource())
    resource = await fetch_schedule_resource(uri)
    assert resource.schedule_spec is None
    assert len(resource.templates) == 2


async def test_create_schedule_with_resource(httpx2_mock: respx.Router, aclient: AsyncClient) -> None:
    """Tests that a schedule is refreshed from its resource when it is
    created.
    """
    uri = make_uri()
    httpx2_mock.get(uri).respond(
        codes.OK, content=make_resource({"cron": "0 12 * * *", "expressions": {"day_obs": "20261101"}})
    )
    schedule_url = await create_schedule(aclient, uri, name_format="%s")
    schedule = await get_schedule(aclient, schedule_url)
    assert schedule["cron"] == "0 12 * * *"
    assert schedule["configuration"] == {"expressions": {"day_obs": "20261101"}, "uri": uri}

    # Without a schedule manifest, the submitted configuration is kept
    uri = make_uri()
    httpx2_mock.get(uri).respond(codes.OK, content=make_resource())
    schedule_url = await create_schedule(aclient, uri, name_format="%s")
    schedule = await get_schedule(aclient, schedule_url)
    # The cron string is normalized, e.g., SUN to 0
    assert schedule["cron"] == "0 0 * * 0"
    assert schedule["configuration"] == {"name_format": "%s", "uri": uri}


async def test_create_schedule_with_unavailable_resource(
    httpx2_mock: respx.Router, aclient: AsyncClient
) -> None:
    """Tests that a schedule is not created when its resource cannot be
    used.
    """
    uri = make_uri()
    httpx2_mock.get(uri).respond(codes.NOT_FOUND)
    name = f"schedule_{uuid4().hex[:8]}"
    x = await aclient.post(
        "/v2/schedules", json={"name": name, "cron": "0 0 * * SUN", "configuration": {"uri": uri}}
    )
    assert x.status_code == codes.BAD_GATEWAY
    assert uri in x.json()["detail"]
    x = await aclient.get(f"/v2/schedules/{name}")
    assert x.status_code == codes.NOT_FOUND


async def test_patch_schedule_with_resource(httpx2_mock: respx.Router, aclient: AsyncClient) -> None:
    """Tests that a schedule is refreshed when it is given a new resource, and
    that other updates are applied as requested.
    """
    schedule_url = await create_schedule(aclient)
    uri = make_uri()
    route = httpx2_mock.get(uri).respond(codes.OK, content=make_resource({"cron": "0 12 * * *"}))

    x = await aclient.patch(schedule_url, json={"configuration": {"uri": uri}})
    assert x.status_code == codes.OK
    schedule = await get_schedule(aclient, schedule_url)
    assert schedule["cron"] == "0 12 * * *"
    assert route.call_count == 1

    # An update that does not change the resource is applied, not refreshed
    x = await aclient.patch(schedule_url, json={"configuration": {"name_format": "%s"}})
    assert x.status_code == codes.OK
    schedule = await get_schedule(aclient, schedule_url)
    assert schedule["configuration"]["name_format"] == "%s"
    assert route.call_count == 1

    # A new resource that cannot be used is not applied
    bad_uri = make_uri()
    httpx2_mock.get(bad_uri).respond(codes.INTERNAL_SERVER_ERROR)
    x = await aclient.patch(schedule_url, json={"configuration": {"uri": bad_uri}})
    assert x.status_code == codes.BAD_GATEWAY
    schedule = await get_schedule(aclient, schedule_url)
    assert schedule["configuration"]["uri"] == uri


async def test_refresh_schedule_api(httpx2_mock: respx.Router, aclient: AsyncClient) -> None:
    """Tests refreshing a schedule from its resource with the refresh API."""
    # A schedule without a resource is not changed
    schedule_url = await create_schedule(aclient)
    x = await aclient.post(f"{schedule_url}/refresh")
    assert x.status_code == codes.NO_CONTENT

    # A schedule whose resource has no schedule manifest is not changed
    uri = make_uri()
    route = httpx2_mock.get(uri).respond(codes.OK, content=make_resource())
    schedule_url = await create_schedule(aclient, uri)
    x = await aclient.post(f"{schedule_url}/refresh")
    assert x.status_code == codes.NO_CONTENT

    # The resource's new schedule manifest replaces the configuration
    route.respond(codes.OK, content=make_resource({"cron": "0 12 * * *", "auto_start": False}))
    x = await aclient.post(f"{schedule_url}/refresh")
    assert x.status_code == codes.OK
    assert x.headers["Self"] == schedule_url
    changes = x.json()["changes"]
    assert changes == {
        "cron": {"from": "0 0 * * 0", "to": "0 12 * * *"},
        "auto_start": {"from": None, "to": False},
    }
    schedule = await get_schedule(aclient, schedule_url)
    assert schedule["cron"] == "0 12 * * *"
    assert schedule["configuration"]["auto_start"] is False
    assert schedule["metadata"]["updated_by"] == "testuser"

    # The refresh is audited
    x = await aclient.get(
        "/v2/audit/", params={"object": schedule_url.split("/")[-1], "object_type": "schedule"}
    )
    assert x.status_code == codes.OK
    (audit,) = x.json()
    assert audit["actor"] == "testuser"
    assert audit["context"] == {"uri": uri, "changes": changes}

    # A refresh with no new changes changes nothing
    x = await aclient.post(f"{schedule_url}/refresh")
    assert x.status_code == codes.NO_CONTENT

    # A resource that cannot be used is reported
    route.respond(codes.INTERNAL_SERVER_ERROR)
    x = await aclient.post(f"{schedule_url}/refresh")
    assert x.status_code == codes.BAD_GATEWAY

    # A request without an identifiable actor is rejected
    request = aclient.build_request("POST", f"{schedule_url}/refresh")
    del request.headers["X-Auth-Request-User"]
    x = await aclient.send(request)
    assert x.status_code == codes.UNPROCESSABLE_ENTITY


async def test_scheduled_job_refreshes_schedule(httpx2_mock: respx.Router, aclient: AsyncClient) -> None:
    """Tests that a schedule is refreshed from its resource when it runs, and
    that the new campaign uses the refreshed configuration.
    """
    uri = make_uri()
    route = httpx2_mock.get(uri).respond(
        codes.OK, content=make_resource({"name_format": f"{uuid4().hex[:8]}_%Y%m%d%H%M%S%f"})
    )
    schedule_url = await create_schedule(aclient, uri)
    schedule_id = UUID(schedule_url.split("/")[-1])

    nonce = uuid4().hex[:8]
    route.respond(
        codes.OK,
        content=make_resource(
            {"cron": "0 12 * * *", "name_format": f"{nonce}", "expressions": {"day_obs": "20261101"}}
        ),
    )
    result = await daemon_scheduled_job(schedule_id=schedule_id, oneshot=True)
    assert result is JobEventReturnCode.SUCCESS

    schedule = await get_schedule(aclient, schedule_url)
    assert schedule["cron"] == "0 12 * * *"
    assert schedule["configuration"]["expressions"] == {"day_obs": "20261101"}

    x = await aclient.get(f"/v2/campaigns/resource_campaign_{nonce}")
    assert x.status_code == codes.OK
    x = await aclient.get(x.headers["Manifests"])
    assert x.status_code == codes.OK
    (butler,) = [m for m in x.json() if m["name"] == "resource_butler"]
    assert butler["spec"]["predicates"] == ["day_obs=20261101"]

    x = await aclient.get("/v2/audit/", params={"object": str(schedule_id), "object_type": "schedule"})
    assert [audit["actor"] for audit in x.json()] == ["scheduler"]
