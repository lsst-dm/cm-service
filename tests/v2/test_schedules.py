"""Tests for schedules"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

import pytest
import yaml
from apscheduler import events
from httpx import AsyncClient, codes
from pydantic import ValidationError

from lsst.cmservice.common.daemon_v2 import DaemonContext, consider_schedules
from lsst.cmservice.common.scheduler import Scheduler
from lsst.cmservice.common.templates import build_sandbox_and_render_templates, prepare_orm_from_manifest
from lsst.cmservice.models.api.manifests import (
    CampaignManifest,
    EdgeManifest,
    Manifest,
    ManifestModel,
    NodeManifest,
)
from lsst.cmservice.models.api.schedules import ScheduleConfiguration
from lsst.cmservice.models.db.schedules import ManifestTemplateBase
from lsst.cmservice.models.lib.transformer import manifest_to_orm

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "schedule"


# Utility functions
def expect_exception(exc: type[Exception] | None) -> AbstractContextManager:
    return pytest.raises(exc) if exc else nullcontext()


# Test Cases
def make_schedule_no_manifests(**overrides: dict) -> dict:
    return {
        "name": f"schedule_with_no_manifests_{uuid4().hex[:8]}",
        "cron": "0 0 * * SUN",
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
                            - obs_day>='{{ today | as_obs_day }}'
                            - obs_day<'{{ tomorrow | as_obs_day }}'
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
        pytest.param(ScheduleTestCase(post_data={}, expected_code=codes.UNPROCESSABLE_ENTITY), id="bad"),
        pytest.param(ScheduleTestCase(), id="empty"),
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
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
        case "bad":
            # Nothing was created
            assert "Self" not in x.headers
            y = await aclient.delete(f"/v2/schedules/{uuid4()}")
            assert y.status_code == codes.NOT_FOUND
        case _:
            pass


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
            new_schedule = x.json()
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
        ManifestTemplateBase(
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
        assert "{{" not in manifest
        assert "}}" not in manifest


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

    def listener(e: events.JobEvent) -> None:
        """A simple event listener for the test, collects events into a list"""
        job_events.append(e.code)
        if e.code == events.EVENT_JOB_EXECUTED or e.code == events.EVENT_JOB_ERROR:
            job_signal.set()

    # Create and enable the schedule
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code

    x = await aclient.patch(
        x.headers["Self"], json={"is_enabled": True, "configuration": {"name_format": "%Y%m%d"}}
    )
    assert x.status_code == codes.OK
    x = await aclient.get(x.headers["Self"])
    assert x.status_code == codes.OK

    new_schedule = x.json()
    assert new_schedule["is_enabled"]
    assert new_schedule["next_run_at"] is not None
    assert new_schedule["configuration"]["name_format"] == "%Y%m%d"

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

    # Closing the loop for this test, we check the side effects:
    # - we should have a new campaign
    expected_campaign_name = f"sample_campaign_{right_now:%Y%m%d}"
    x = await aclient.head(f"/v2/campaigns/{expected_campaign_name}")
    assert x.status_code == codes.NO_CONTENT

    # - Check the rendered template variable in a butler manifest
    x = await aclient.get(f"{x.headers['Self']}/manifests")
    assert x.status_code == codes.OK
    campaign_manifests = x.json()
    assert len(campaign_manifests) > 0
    butler_manifest = campaign_manifests[0]
    assert f"obs_day>='{right_now:%Y%m%d}'" in butler_manifest["spec"]["predicates"]
