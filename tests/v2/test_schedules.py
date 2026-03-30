"""Tests for schedules"""

from dataclasses import dataclass
from textwrap import dedent
from uuid import uuid4

import pytest
import yaml
from httpx import AsyncClient, codes

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


@dataclass
class ScheduleTestCase:
    post_data: dict
    expected_code: int


@pytest.fixture
def test_case(request) -> ScheduleTestCase:
    return request.param


# Test Cases
SCHEDULE_NO_MANIFESTS = {
    "name": "schedule_with_no_manifests",
    "cron": "0 0 * * SUN",
}

SCHEDULE_WITH_MANIFESTS = {
    "name": "schedule_with_manifests",
    "cron": "0 */4 * * WED",
    "expressions": {
        "today": "datetime.now()",
        "tomorrow": "datetime.now()",
    },
    "templates": [
        {
            "kind": "node",
            "manifest": yaml.safe_load(
                dedent("""\
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
            """)
            ),
        },
    ],
}


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
        pytest.param(
            ScheduleTestCase(post_data=SCHEDULE_NO_MANIFESTS, expected_code=codes.NO_CONTENT), id="empty"
        ),
        pytest.param(
            ScheduleTestCase(post_data=SCHEDULE_WITH_MANIFESTS, expected_code=codes.NO_CONTENT), id="full"
        ),
    ],
    indirect=["test_case"],
)
async def test_post_new_schedule(aclient: AsyncClient, test_case: ScheduleTestCase) -> None:
    """Tests creating a new schedule"""
    x = await aclient.post("/v2/schedules", json=test_case.post_data)
    assert x.status_code == test_case.expected_code
    ...
