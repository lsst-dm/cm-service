"""Tests for schedules"""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from textwrap import dedent
from typing import Any
from uuid import UUID, uuid4

import pytest
import respx
import yaml
from apscheduler import events
from httpx2 import AsyncClient, codes
from pydantic import ValidationError

from lsst.cmservice.common.daemon_v2 import DaemonContext, consider_schedules, daemon_scheduled_job
from lsst.cmservice.common.scheduler import JobEventReturnCode, Scheduler
from lsst.cmservice.common.templates import (
    ManifestRenderingError,
    build_sandbox_and_render_templates,
    compile_user_expressions,
)
from lsst.cmservice.models.api.manifests import (
    CampaignManifest,
    EdgeManifest,
    Manifest,
    ManifestModel,
    NodeManifest,
)
from lsst.cmservice.models.api.schedules import (
    ScheduleConfiguration,
    ScheduleOneshot,
    ScheduleTrigger,
    ScheduleTriggerBinding,
)
from lsst.cmservice.models.db.schedules import CreateManifestTemplate
from lsst.cmservice.models.enums import ManifestKind
from lsst.cmservice.models.lib.timestamp import now_utc
from lsst.cmservice.models.lib.transformer import manifest_to_orm, prepare_orm_from_manifest

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "schedule"


# Utility functions
def expect_exception(exc: type[Exception] | None) -> AbstractContextManager:
    return pytest.raises(exc) if exc else nullcontext()


# Test Cases
def make_schedule_no_manifests(**overrides: dict) -> dict:
    nonce = uuid4().hex[:8]
    return {
        "name": f"schedule_with_no_manifests_{nonce}",
        "cron": "0 0 * * SUN",
    }


def make_schedule_with_bad_manifests(**overrides: dict) -> dict:
    return {
        "name": f"schedule_with_bad_manifests_{uuid4().hex[:8]}",
        "cron": "0 0 * * 0",
        "configuration": {},
        "templates": [
            {
                "kind": "campaign",
                "manifest": dedent("""\
                    apiVersion: io.lsst.cmservice/v1
                    kind: campaign
                    metadata:
                        name: sample_campaign
                    spec: {}
                """),
            },
            {
                "kind": "node",
                "manifest": dedent("""\
                    ---
                    apiVersion: io.lsst.cmservice/v1
                    kind: node
                    metadata:
                        kind: start
                        name: START
                    spec: {}
                """),
            },
        ],
    }


def make_schedule_with_manifests(**overrides: dict) -> dict:
    return {
        "name": f"schedule_with_manifests_{uuid4().hex[:8]}",
        "cron": "0 */4 * * WED",
        "configuration": {
            "expressions": {
                "today": "datetime.now()",
                "tomorrow": "datetime.now() + timedelta(days=1)",
            },
        },
        "templates": [
            {
                "kind": "campaign",
                "manifest": dedent("""\
                    apiVersion: io.lsst.cmservice/v1
                    kind: campaign
                    metadata:
                        name: sample_campaign
                    spec: {}
                """),
            },
            {
                "kind": "node",
                "manifest": dedent("""\
                    ---
                    apiVersion: io.lsst.cmservice/v1
                    kind: node
                    metadata:
                        kind: step
                        name: step_1abc
                    spec:
                        bps:
                            pipeline_yaml: ${DRP_PIPE_DIR}/path/to/file.yaml#step1a,step1b,step1c
                        groups:
                            dimension: tract
                            split_by: values
                            values:
                            - 1
                            - 2
                            - 3
                            - 4
                            - 5
                """),
            },
            {
                "kind": "butler",
                "manifest": dedent("""\
                    ---
                    apiVersion: io.lsst.cmservice/v1
                    kind: butler
                    metadata:
                        name: repo_main_lsstcam_defaults
                        namespace: b67094a8-c44f-50b7-a2db-81c95a16fd29
                        version: 0
                    spec:
                        collections:
                            campaign_input:
                            - LSSTCam/defaults
                        predicates:
                            - instrument='LSSTCam'
                            - skymap='lsst_cells_v1'
                            - day_obs>='${{ today | as_day_obs }}'
                            - day_obs<'${{ tomorrow | as_day_obs }}'
                        repo: /repo/main
                    """),
            },
        ],
    }


@dataclass
class ScheduleTestCase:
    post_data: dict = field(default_factory=make_schedule_no_manifests)
    expected_code: int = codes.CREATED


@pytest.fixture
def test_case(request: pytest.FixtureRequest) -> ScheduleTestCase:
    return request.param


@pytest.fixture(scope="module")
def manifest_yaml() -> Callable[[str], dict]:
    """Fixture for loading manifest templates from a file and providing a
    callable to retrieve them by name.
    """

    def _get_fixture(fixture_name: str) -> dict:
        return fixture_data[fixture_name]

    with (FIXTURE_DIR / "manifest_templates.yaml").open("r") as f:
        fixture_data = yaml.safe_load(f)
    return _get_fixture


async def test_list_no_schedules(aclient: AsyncClient) -> None:
    """Tests listing schedules when there are no schedules available."""
    x = await aclient.get("/v2/schedules")
    assert x.is_success
    assert len(x.json()) == 0

    x = await aclient.get(f"/v2/schedules/{uuid4()}")
    assert x.status_code == codes.NOT_FOUND

    x = await aclient.get("/v2/schedules/no_such_schedule")
    assert x.status_code == codes.NOT_FOUND


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(post_data={}, expected_code=codes.UNPROCESSABLE_ENTITY), id="bad1"),
        pytest.param(ScheduleTestCase(), id="empty"),
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
        pytest.param(
            ScheduleTestCase(
                expected_code=codes.UNPROCESSABLE_ENTITY, post_data=make_schedule_with_bad_manifests()
            ),
            id="bad2",
        ),
    ],
    indirect=["test_case"],
)
async def test_post_new_schedule(
    aclient: AsyncClient, test_case: ScheduleTestCase, request: pytest.FixtureRequest
) -> None:
    """Tests creating a new schedule"""
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code

    match request.node.callspec.id:
        case "full":
            y = await aclient.get("/v2/schedules")
            assert y.status_code == codes.OK
            r = y.json()
            assert len(r) > 0
            # the get collections route does not return relationship fields
            assert "templates" not in r[0]
            y = await aclient.get(x.headers["Templates"])
            assert y.status_code == codes.OK
            assert len(y.json()) > 0
            y = await aclient.delete(x.headers["Self"])
            assert y.status_code == codes.NO_CONTENT
            # it is not an error to GET templates for a nonexistent schedule;
            # there will be an empty list
            y = await aclient.get(x.headers["Templates"])
            assert y.status_code == codes.OK
            # Ensure the cascade delete has removed the templates when the
            # schedule was removed.
            assert len(y.json()) == 0
        case "empty":
            y = await aclient.get(x.headers["Templates"])
            assert y.status_code == codes.OK
            assert len(y.json()) == 0
            y = await aclient.delete(x.headers["Self"])
            y = await aclient.head(x.headers["Self"])
            assert y.status_code == codes.NOT_FOUND
        case "bad1" | "bad2":
            # Nothing was created
            assert "Self" not in x.headers
            y = await aclient.delete(f"/v2/schedules/{uuid4()}")
            assert y.status_code == codes.NOT_FOUND
        case _:
            pass


@pytest.mark.parametrize(
    "configuration,fields",
    [
        ({"cron": "0 12 * * *"}, "cron"),
        ({"name_format": "%s", "is_enabled": True, "metadata": {}}, "is_enabled, metadata"),
    ],
    ids=["cron", "fields and aliases"],
)
async def test_schedule_configuration_fields(aclient: AsyncClient, configuration: dict, fields: str) -> None:
    """Tests that a schedule's own fields are rejected in its configuration,
    where they would have no effect.
    """
    post_data = make_schedule_no_manifests() | {"configuration": configuration}
    x = await aclient.post("/v2/schedules", json=post_data)
    assert x.status_code == codes.UNPROCESSABLE_ENTITY
    assert x.json()["detail"].endswith(fields)

    x = await aclient.post(
        "/v2/schedules", json=make_schedule_no_manifests() | {"configuration": {"name_format": "%s"}}
    )
    assert x.status_code == codes.CREATED
    schedule_url = x.headers["Self"]
    x = await aclient.patch(schedule_url, json={"configuration": configuration})
    assert x.status_code == codes.UNPROCESSABLE_ENTITY
    assert x.json()["detail"].endswith(fields)

    # The schedule is unchanged
    x = await aclient.get(schedule_url)
    assert x.json()[0]["configuration"] == {"name_format": "%s"}


async def test_patch_schedule_configuration(aclient: AsyncClient) -> None:
    """Tests that a PATCH updates only the configuration fields it sets,
    without adding defaults, and that the updated configuration is validated.
    """
    # Explicit values that equal their defaults are kept as set
    configuration = {"auto_start": True, "name_format": "%Y%m%d", "expressions": {"day_obs": "'20261101'"}}
    x = await aclient.post(
        "/v2/schedules", json=make_schedule_no_manifests() | {"configuration": configuration}
    )
    assert x.status_code == codes.CREATED
    schedule_url = x.headers["Self"]

    async def stored_configuration() -> dict:
        x = await aclient.get(schedule_url)
        assert x.status_code == codes.OK
        return x.json()[0]["configuration"]

    # A PATCH without a configuration does not change it
    x = await aclient.patch(schedule_url, json={"is_enabled": True})
    assert x.status_code == codes.OK
    assert await stored_configuration() == configuration

    # A configuration PATCH changes only the fields it sets
    x = await aclient.patch(schedule_url, json={"configuration": {"name_format": "%s"}})
    assert x.status_code == codes.OK
    configuration["name_format"] = "%s"
    assert await stored_configuration() == configuration

    # An invalid configuration PATCH is rejected without changing the schedule
    for update in [{"expressions": {"my-var": ""}}, {"auto_start": "maybe"}]:
        x = await aclient.patch(schedule_url, json={"configuration": update})
        assert x.status_code == codes.UNPROCESSABLE_ENTITY
        assert await stored_configuration() == configuration


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(), id="empty"),
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
    ],
    indirect=["test_case"],
)
async def test_put_patch_schedule(
    aclient: AsyncClient, test_case: ScheduleTestCase, request: pytest.FixtureRequest
) -> None:
    """Tests the schedule update put and patch operations"""
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code

    match request.node.callspec.id:
        case "empty":
            x = await aclient.put(x.headers["Self"], json={})
            assert x.status_code == codes.METHOD_NOT_ALLOWED
        case "full":
            x = await aclient.patch(
                x.headers["Self"], json={"is_enabled": True, "configuration": {"auto_start": False}}
            )
            assert x.status_code == codes.OK
            x = await aclient.get(x.headers["Self"])
            assert x.status_code == codes.OK
            new_schedule = x.json()[0]
            assert new_schedule["is_enabled"]
            assert new_schedule["next_run_at"] is not None
            assert "mtime" in new_schedule["metadata"]

            new_schedule_config = ScheduleConfiguration(**new_schedule["configuration"])
            assert new_schedule_config.auto_start is False
            # Ensure expressions have been preserved by the patch operation
            assert len(new_schedule_config.expressions) > 0
            x = await aclient.delete(x.headers["Self"])


@pytest.mark.parametrize(
    "fixture_name,manifest_model,raises",
    [
        ("campaign_good", CampaignManifest, None),
        ("node_good", NodeManifest, None),
        ("edge_good", EdgeManifest, ValueError),  # This edge has not had the correct business logic applied
        ("butler_manifest_good", ManifestModel, None),
    ],
)
async def test_orm_from_manifest(
    manifest_yaml: Callable[[str], dict], fixture_name: str, manifest_model: Manifest, raises: type[Exception]
) -> None:
    """Tests the manifest_to_orm transformer function."""
    manifest = manifest_yaml(fixture_name)
    manifest_request = manifest_model.model_validate(manifest)

    # the function takes a request model that has already had business logic
    # applied and returns an ORM
    with expect_exception(raises):
        orm_object = manifest_to_orm(manifest_request)

    if not raises:
        assert orm_object is not None


@pytest.mark.parametrize(
    "fixture_name,use_namespace,raises",
    [
        ("campaign_good", False, None),
        ("campaign_bad", False, ValidationError),
        ("node_good", True, None),
        ("edge_good", True, None),
        ("edge_bad", False, RuntimeError),
        ("butler_manifest_good", True, None),
    ],
)
async def test_template_to_orm(
    *,
    manifest_yaml: Callable[[str], dict],
    fixture_name: str,
    use_namespace: bool,
    raises: type[Exception],
) -> None:
    """Tests the prepare_orm_from_manifest transformer function."""
    manifest = manifest_yaml(fixture_name)
    namespace = uuid4() if use_namespace else None

    # The function takes a complete (rendered) manifest dict and returns an
    # ORM after applying standard scheduler-focused business logic
    with expect_exception(raises):
        orm_object = await prepare_orm_from_manifest(manifest, namespace)

    if not raises:
        assert orm_object is not None


@pytest.mark.parametrize(
    "fixture_name,raises",
    [("butler_manifest_good", None), ("lsst_manifest_good", None)],
)
async def test_template_render(
    manifest_yaml: Callable[[str], dict], fixture_name: str, raises: type[Exception]
) -> None:
    """Tests the sandbox rendering of a template manifest."""
    template = manifest_yaml(fixture_name)
    context = ScheduleConfiguration(
        expressions={"today": "datetime.now()", "yesterday": "datetime.now() - timedelta(days=1)"}
    )
    templates = [
        CreateManifestTemplate(
            name=uuid4().hex[0:8],
            kind=template["kind"],
            manifest=yaml.dump(template),
            metadata_={},
        )
    ]

    # The function takes a raw manifest template string and a mapping of
    # variable to python expressions.
    with expect_exception(raises):
        manifests = await build_sandbox_and_render_templates(context, templates, as_orm=False)
        manifest = yaml.dump(manifests[0])

    # successful rendering means no leftover variable placeholders
    if not raises:
        assert "${{" not in manifest
        assert "{{" not in manifest
        assert "}}" not in manifest


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("20261101", 20261101),
        ("'20261101'", "20261101"),
        ("[1, 2, 3, 4]", [1, 2, 3, 4]),
        ('["a", "b", "c"]', ["a", "b", "c"]),
        ('{"a": 1}', {"a": 1}),
        ("True", True),
        ("None", None),
        ("datetime(2026, 11, 1, tzinfo=timezone.utc)", datetime(2026, 11, 1, tzinfo=UTC)),
    ],
)
@pytest.mark.parametrize("strict", [True, False], ids=["strict", "lenient"])
async def test_compile_literal_expressions(expression: str, expected: Any, *, strict: bool) -> None:
    """Tests that expressions may be simple literal assignments."""
    assert compile_user_expressions({"value": expression}, strict=strict) == {"value": expected}


@pytest.mark.parametrize("expression", ["slac", "datetime.nope", "0101", "datetime.now(", "nope.attr"])
async def test_compile_strict_expressions(expression: str) -> None:
    """Tests that strict compilation rejects expressions that would otherwise
    silently evaluate to None or fail later.
    """
    with pytest.raises(ManifestRenderingError, match="'value'"):
        compile_user_expressions({"value": expression}, strict=True)


async def test_compile_lenient_undefined_expression() -> None:
    """Tests that lenient compilation preserves the behavior of evaluating an
    undefined value as None.
    """
    assert compile_user_expressions({"value": "slac"}) == {"value": None}


async def test_template_expressions() -> None:
    """Tests that valid template expressions are plain mappings."""
    expressions = {"today": "datetime.now()", "day_obs": "20261101"}
    assert ScheduleOneshot(expressions=expressions).expressions == expressions

    protocol = "type=='complete' && {day_obs: day_obs} || `null`"
    configuration = ScheduleConfiguration(
        expressions={"today": "datetime.now()"},
        triggers=[ScheduleTriggerBinding(source="kafka", channel="inbound", protocol=protocol)],
    )
    assert configuration.expressions == {"today": "datetime.now()"}
    assert configuration.model_dump()["triggers"] == [
        {"source": "kafka", "channel": "inbound", "protocol": protocol}
    ]


@pytest.mark.parametrize(
    "expressions",
    [{"my-var": "1"}, {"1st": "1"}, {"": "1"}, {"x": ""}, {"x": "  "}, {"x": 1}],
    ids=["dash", "leading digit", "empty name", "empty", "blank", "not a string"],
)
async def test_invalid_template_expressions(expressions: dict) -> None:
    """Tests that unusable expression names and empty expressions are
    rejected.
    """
    with pytest.raises(ValidationError):
        ScheduleOneshot(expressions=expressions)


async def test_template_render_literals() -> None:
    """Tests rendering templates with literal expressions."""
    context = ScheduleConfiguration(
        expressions={"day_obs": "20261101", "x": "[1, 2, 3, 4]", "y": '["a", "b", "c"]'}
    )
    templates = [
        CreateManifestTemplate(
            name=uuid4().hex[0:8],
            kind=ManifestKind.butler,
            manifest=dedent("""\
                apiVersion: io.lsst.cmservice/v1
                kind: butler
                metadata:
                    name: literal_butler
                spec:
                    x: ${{ x }}
                    y: ${{ y }}
                    predicates:
                        - day_obs=${{ day_obs }}
                        - ${{ x | sql_in(field="detector") }}
                        - ${{ y | sql_not_in(field="band") }}
            """),
        )
    ]
    manifests = await build_sandbox_and_render_templates(context, templates, as_orm=False)
    spec = manifests[0]["spec"]
    assert spec["x"] == [1, 2, 3, 4]
    assert spec["y"] == ["a", "b", "c"]
    assert spec["predicates"] == ["day_obs=20261101", "detector IN (1,2,3,4)", "band NOT IN ('a','b','c')"]


async def test_template_render_overrides() -> None:
    """Tests that override values are merged over the values of the compiled
    expressions, and that the campaign records the values used to render.
    """
    context = ScheduleConfiguration(expressions={"today": "datetime(2026, 11, 1)", "x": "1"})
    templates = [
        CreateManifestTemplate(
            name=uuid4().hex[0:8],
            kind=ManifestKind.campaign,
            manifest=dedent("""\
                apiVersion: io.lsst.cmservice/v1
                kind: campaign
                metadata:
                    name: values_campaign
                spec:
                    day_obs: ${{ today | as_day_obs }}
                    x: ${{ x }}
                    y: ${{ y }}
            """),
        )
    ]
    (campaign, *_) = await build_sandbox_and_render_templates(context, templates, as_orm=False)
    assert campaign["metadata"]["values"] == {"today": "2026-11-01T00:00:00", "x": 1}

    (campaign, *_) = await build_sandbox_and_render_templates(
        context, templates, overrides={"x": 2, "y": "v30"}, as_orm=False
    )
    assert campaign["spec"].items() >= {"day_obs": 20261101, "x": 2, "y": "v30"}.items()
    assert campaign["metadata"]["values"] == {"today": "2026-11-01T00:00:00", "x": 2, "y": "v30"}


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
    ],
    indirect=["test_case"],
)
async def test_daemon_schedule(
    aclient: AsyncClient, test_case: ScheduleTestCase, daemon_context: DaemonContext
) -> None:
    """Tests creating a new schedule and processing the schedule with the
    daemon service layer.
    """
    job_events: list[int] = []
    job_signal = asyncio.Event()
    right_now = datetime.now(tz=UTC)
    nonce = uuid4().hex[:8]

    def listener(e: events.JobEvent) -> None:
        """A simple event listener for the test, collects events into a list"""
        job_events.append(e.code)
        if e.code == events.EVENT_JOB_EXECUTED or e.code == events.EVENT_JOB_ERROR:
            job_signal.set()

    # Create and enable the schedule
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code

    x = await aclient.patch(
        x.headers["Self"], json={"is_enabled": True, "configuration": {"name_format": f"{nonce}_%Y%m%d"}}
    )
    assert x.status_code == codes.OK
    x = await aclient.get(x.headers["Self"])
    assert x.status_code == codes.OK

    new_schedule = x.json()[0]
    assert new_schedule["is_enabled"]
    assert new_schedule["next_run_at"] is not None
    assert new_schedule["configuration"]["name_format"] == f"{nonce}_%Y%m%d"

    scheduler: Scheduler
    async with daemon_context as dc:
        scheduler = dc.app.state.scheduler
        assert scheduler.scheduler.running
        assert not len(scheduler.scheduler.get_jobs())

        scheduler.scheduler.add_listener(listener, events.EVENT_ALL)
        await consider_schedules(dc)
        assert len(scheduler.scheduler.get_jobs()) == 1

        job = scheduler.scheduler.get_jobs()[0]
        assert job.next_run_time >= right_now
        # Reschedule the job in the past; trigger scheduler catch-up
        job.reschedule(trigger="date", run_date=right_now - timedelta(minutes=1))

    # wait up to 3 seconds for the job completion event.
    await asyncio.wait_for(job_signal.wait(), timeout=3.0)

    assert events.EVENT_JOB_ERROR not in job_events
    assert events.EVENT_JOB_EXECUTED in job_events

    # Delete the schedule
    x = await aclient.delete(x.headers["Self"])
    assert x.is_success

    # Closing the loop for this test, we check the side effects:
    # - we should have a new campaign
    expected_campaign_name = f"sample_campaign_{nonce}_{right_now:%Y%m%d}"
    x = await aclient.head(f"/v2/campaigns/{expected_campaign_name}")
    assert x.status_code == codes.NO_CONTENT

    # - Check the rendered template variable in a butler manifest
    x = await aclient.get(f"{x.headers['Self']}/manifests")
    assert x.status_code == codes.OK
    campaign_manifests = x.json()
    assert len(campaign_manifests) > 0
    butler_manifest = campaign_manifests[0]
    assert f"day_obs>='{right_now:%Y%m%d}'" in butler_manifest["spec"]["predicates"]


async def test_one_shot_scheduler() -> None:
    """Tests the one-shot scheduler."""
    sentinel = asyncio.Event()
    job_target = False

    def job_function() -> None:
        nonlocal job_target
        job_target = not job_target
        sentinel.set()

    async with Scheduler.get_one_shot_scheduler() as scheduler:
        scheduler.add_job(job_function, "interval", id="test_job")
        await asyncio.wait_for(sentinel.wait(), timeout=5.0)
        assert job_target is True


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
    ],
    indirect=["test_case"],
)
async def test_one_shot_api(aclient: AsyncClient, test_case: ScheduleTestCase) -> None:
    """Creates a schedule and runs it using the oneshot API."""
    today = now_utc()

    async def check_oneshot_complete() -> bool:
        """checks for the existence of the expected new campaign"""
        while True:
            y = await aclient.get(f"/v2/campaigns/sample_campaign_{today:%Y%m%d%H%M}")
            if y.status_code == codes.OK:
                return True
            else:
                await asyncio.sleep(1.0)

    # Create and enable the schedule
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code
    schedule_url = x.headers["Self"]

    x = await aclient.patch(
        schedule_url, json={"is_enabled": True, "configuration": {"name_format": "%Y%m%d%H%M"}}
    )
    assert x.status_code == codes.OK
    x = await aclient.get(schedule_url)
    assert x.status_code == codes.OK

    new_schedule = x.json()[0]
    assert new_schedule["is_enabled"]
    assert new_schedule["next_run_at"] is not None
    assert new_schedule["configuration"]["name_format"] == "%Y%m%d%H%M"

    x = await aclient.post(f"{schedule_url}/oneshot")
    assert x.status_code == codes.CONFLICT
    assert "may not be enabled" in x.json()["detail"]

    x = await aclient.patch(schedule_url, json={"is_enabled": False})
    assert x.status_code == codes.OK

    x = await aclient.post(f"{schedule_url}/oneshot")
    assert x.status_code == codes.ACCEPTED

    await asyncio.wait_for(check_oneshot_complete(), timeout=10.0)
    x = await aclient.get(f"/v2/campaigns/sample_campaign_{today:%Y%m%d%H%M}")
    assert x.status_code == codes.OK
    x = await aclient.get(x.headers["nodes"])
    assert x.status_code == codes.OK
    assert len(x.json()) == 3


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
    ],
    indirect=["test_case"],
)
async def test_one_shot_api_overrides(aclient: AsyncClient, test_case: ScheduleTestCase) -> None:
    """Runs a schedule using the oneshot API with expression overrides and an
    idempotency key.
    """
    today = now_utc()
    nonce = uuid4().hex[:8]
    idempotency_key = uuid4().hex
    campaign_name = f"sample_campaign_{nonce}_{today:%Y%m%d}"
    overrides = {"today": "datetime(2020, 1, 1)", "tomorrow": "datetime(2020, 1, 2)"}

    async def check_oneshot_complete() -> bool:
        """checks for the existence of the expected new campaign"""
        while True:
            y = await aclient.head(f"/v2/campaigns/{campaign_name}")
            if y.status_code == codes.NO_CONTENT:
                return True
            else:
                await asyncio.sleep(1.0)

    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code
    schedule_url = x.headers["Self"]

    x = await aclient.patch(
        schedule_url, json={"is_enabled": False, "configuration": {"name_format": f"{nonce}_%Y%m%d"}}
    )
    assert x.status_code == codes.OK

    # A request without an identifiable actor is rejected
    request = aclient.build_request("POST", f"{schedule_url}/oneshot")
    del request.headers["X-Auth-Request-User"]
    x = await aclient.send(request)
    assert x.status_code == codes.UNPROCESSABLE_ENTITY
    x = await aclient.post(f"{schedule_url}/oneshot", headers={"X-Auth-Request-User": ""})
    assert x.status_code == codes.UNPROCESSABLE_ENTITY

    # An override expression that cannot be evaluated is rejected
    # - a syntax error in the expression
    x = await aclient.post(f"{schedule_url}/oneshot", json={"expressions": {"today": "datetime.now("}})
    assert x.status_code == codes.UNPROCESSABLE_ENTITY
    # - an unquoted string, which is an undefined name rather than a literal
    x = await aclient.post(f"{schedule_url}/oneshot", json={"expressions": {"site": "slac"}})
    assert x.status_code == codes.UNPROCESSABLE_ENTITY
    assert "quote string literals" in x.json()["detail"]
    # - a name that is not an identifier, which a template would parse as an
    #   expression (`my - var`) rather than as a variable
    x = await aclient.post(f"{schedule_url}/oneshot", json={"expressions": {"my-var": "1"}})
    assert x.status_code == codes.UNPROCESSABLE_ENTITY

    x = await aclient.post(
        f"{schedule_url}/oneshot",
        json={"expressions": overrides},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert x.status_code == codes.ACCEPTED

    await asyncio.wait_for(check_oneshot_complete(), timeout=10.0)
    x = await aclient.get(f"/v2/campaigns/{campaign_name}")
    assert x.status_code == codes.OK
    campaign_url = x.headers["Self"]
    assert x.json()["metadata"]["trigger"] == {
        "source": "api",
        "actor": "testuser",
        "schedule": schedule_url.split("/")[-1],
        "key": idempotency_key,
    }
    # The values used to render the templates are recorded with the campaign
    assert x.json()["metadata"]["values"] == {
        "today": "2020-01-01T00:00:00",
        "tomorrow": "2020-01-02T00:00:00",
    }

    # The overrides are used to render the templates
    x = await aclient.get(f"{campaign_url}/manifests")
    assert x.status_code == codes.OK
    butler_manifest = x.json()[0]
    assert "day_obs>='20200101'" in butler_manifest["spec"]["predicates"]
    assert "day_obs<'20200102'" in butler_manifest["spec"]["predicates"]

    # The overrides are not persisted to the schedule
    x = await aclient.get(schedule_url)
    assert x.status_code == codes.OK
    assert x.json()[0]["configuration"]["expressions"] == test_case.post_data["configuration"]["expressions"]

    # Reusing the idempotency key does not create a new campaign
    x = await aclient.post(
        f"{schedule_url}/oneshot",
        json={"expressions": overrides},
        headers={"Idempotency-Key": idempotency_key},
    )
    assert x.status_code == codes.CONFLICT
    assert x.headers["Location"] == campaign_url


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
    ],
    indirect=["test_case"],
)
async def test_scheduled_job_duplicate_trigger(aclient: AsyncClient, test_case: ScheduleTestCase) -> None:
    """Tests that a scheduled job does not create a second campaign for an
    equivalent trigger, e.g., when two oneshot requests race.
    """
    nonce = uuid4().hex[:8]
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code
    schedule_url = x.headers["Self"]
    x = await aclient.patch(schedule_url, json={"configuration": {"name_format": f"{nonce}_%Y%m%d%H%M%S%f"}})
    assert x.status_code == codes.OK

    schedule_id = UUID(schedule_url.split("/")[-1])
    trigger = ScheduleTrigger(source="test", schedule=schedule_id, key=uuid4().hex)
    result = await daemon_scheduled_job(schedule_id=schedule_id, oneshot=True, trigger=trigger)
    assert result is JobEventReturnCode.SUCCESS
    result = await daemon_scheduled_job(schedule_id=schedule_id, oneshot=True, trigger=trigger)
    assert result is JobEventReturnCode.DUPLICATE_TRIGGER

    # A trigger without a key is never a duplicate
    trigger = ScheduleTrigger(source="test", schedule=schedule_id)
    result = await daemon_scheduled_job(schedule_id=schedule_id, oneshot=True, trigger=trigger)
    assert result is JobEventReturnCode.SUCCESS


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(post_data=make_schedule_no_manifests()), id="external"),
    ],
    indirect=["test_case"],
)
async def test_schedule_from_uri(
    httpx2_mock: respx.Router,
    aclient: AsyncClient,
    daemon_context: DaemonContext,
    test_case: ScheduleTestCase,
) -> None:
    """Test the creation of a scheduled campaign based on templates stored in
    an external URI.
    """
    job_events: list[int] = []
    job_signal = asyncio.Event()
    right_now = datetime.now(tz=UTC)
    nonce = uuid4().hex[:8]

    def listener(e: events.JobEvent) -> None:
        """A simple event listener for the test, collects events into a list"""
        job_events.append(e.code)
        if e.code == events.EVENT_JOB_EXECUTED or e.code == events.EVENT_JOB_ERROR:
            job_signal.set()

    uri = "http://example.com/campaign-spec.yaml"
    content = "\n".join([t["manifest"] for t in make_schedule_with_manifests()["templates"]])
    httpx2_mock.get(uri).respond(codes.OK, content=content)

    # Create the schedule and configure an external URI
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.is_success
    schedule_url = x.headers["Self"]

    x = await aclient.patch(
        schedule_url,
        json={
            "is_enabled": True,
            "configuration": {
                "name_format": f"{nonce}_%Y%m%d",
                "uri": uri,
                "expressions": {
                    "today": "datetime.now()",
                    "tomorrow": "datetime.now() + timedelta(days=1)",
                },
            },
        },
    )
    assert x.is_success

    scheduler: Scheduler
    async with daemon_context as dc:
        scheduler = dc.app.state.scheduler
        assert scheduler.scheduler.running
        assert not len(scheduler.scheduler.get_jobs())

        scheduler.scheduler.add_listener(listener, events.EVENT_ALL)
        await consider_schedules(dc)
        assert len(scheduler.scheduler.get_jobs()) == 1

        job = scheduler.scheduler.get_jobs()[0]
        assert job.next_run_time >= right_now
        # Reschedule the job in the past; trigger scheduler catch-up
        job.reschedule(trigger="date", run_date=right_now - timedelta(minutes=1))

    # wait up to 3 seconds for the job completion event.
    await asyncio.wait_for(job_signal.wait(), timeout=3.0)

    assert events.EVENT_JOB_ERROR not in job_events
    assert events.EVENT_JOB_EXECUTED in job_events

    # Delete the schedule
    x = await aclient.delete(x.headers["Self"])
    assert x.is_success

    # Closing the loop for this test, we check the side effects:
    # - we should have a new campaign
    expected_campaign_name = f"sample_campaign_{nonce}_{right_now:%Y%m%d}"
    x = await aclient.head(f"/v2/campaigns/{expected_campaign_name}")
    assert x.status_code == codes.NO_CONTENT

    # - Check the rendered template variable in a butler manifest
    x = await aclient.get(f"{x.headers['Self']}/manifests")
    assert x.status_code == codes.OK
    campaign_manifests = x.json()
    assert len(campaign_manifests) > 0
    butler_manifest = campaign_manifests[0]
    assert f"day_obs>='{right_now:%Y%m%d}'" in butler_manifest["spec"]["predicates"]
