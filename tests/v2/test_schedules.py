"""Tests for schedules"""

from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from uuid import uuid4

import pytest
from httpx import AsyncClient, codes

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


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
        "expressions": {
            "today": "datetime.now()",
            "tomorrow": "datetime.now() + timedelta(days=1)",
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
                    metadata: {}
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
        ],
    }


@dataclass
class ScheduleTestCase:
    post_data: dict = field(default_factory=make_schedule_no_manifests)
    expected_code: int = codes.CREATED


@pytest.fixture
def test_case(request: pytest.FixtureRequest) -> ScheduleTestCase:
    return request.param


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
            x = await aclient.patch(x.headers["Self"], json={"is_enabled": True})
            assert x.status_code == codes.OK
            x = await aclient.get(x.headers["Self"])
            assert x.status_code == codes.OK
            new_schedule = x.json()
            assert new_schedule["is_enabled"]
            assert new_schedule["next_run_at"] is not None


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(ScheduleTestCase(post_data=make_schedule_with_manifests()), id="full"),
    ],
    indirect=["test_case"],
)
async def test_daemon_schedule(aclient: AsyncClient, test_case: ScheduleTestCase) -> None:
    """Tests creating a new schedule and processing the schedule with the
    daemon service layer.
    """
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code
