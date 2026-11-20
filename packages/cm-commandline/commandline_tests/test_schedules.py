"""Tests for the schedules commands"""

import json
from getpass import getuser
from pathlib import Path
from uuid import uuid4

import pytest
import respx

# respx mocks the httpx2 transport but builds responses as httpx responses
# FIXME refactor with httpx2 when respx (or a replacement) supports it
from httpx import Response as MockResponse
from httpx2 import codes
from pydantic_extra_types.cron import CronStr
from typer.testing import CliRunner, Result

from lsst.cmservice.commandline.cli import app
from lsst.cmservice.models.api.schedules import ScheduleConfiguration

ENDPOINT = "http://cm.example.com/cm-service"


@pytest.fixture
def schedule_id() -> str:
    return str(uuid4())


@pytest.fixture
def schedule_url(schedule_id: str) -> str:
    return f"{ENDPOINT}/v2/schedules/{schedule_id}"


def invoke_oneshot(runner: CliRunner, schedule_id: str, *args: str) -> dict:
    """Invoke the oneshot command and return its JSON output."""
    result = runner.invoke(
        app, ["--output", "json", "--endpoint", ENDPOINT, "schedules", "oneshot", schedule_id, *args]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_oneshot(httpx2_mock: respx.Router, runner: CliRunner, schedule_id: str, schedule_url: str) -> None:
    """Tests a oneshot without overrides sends the same request as before."""
    campaign_url = f"{ENDPOINT}/v2/campaigns/{uuid4()}"
    httpx2_mock.head(schedule_url).mock(
        side_effect=[
            MockResponse(codes.NO_CONTENT, headers={"Self": schedule_url}),
            MockResponse(codes.NO_CONTENT, headers={"Self": schedule_url, "Last-Campaign": campaign_url}),
        ]
    )
    oneshot = httpx2_mock.post(f"{schedule_url}/oneshot").respond(codes.ACCEPTED)
    httpx2_mock.head(campaign_url).respond(codes.NO_CONTENT)

    output = invoke_oneshot(runner, schedule_id)
    assert output["new_campaign_url"] == campaign_url
    assert oneshot.calls.last.request.content == b""
    assert "Idempotency-Key" not in oneshot.calls.last.request.headers


def test_oneshot_overrides(
    httpx2_mock: respx.Router, runner: CliRunner, schedule_id: str, schedule_url: str
) -> None:
    """Tests a oneshot with expression overrides and an idempotency key."""
    campaign_url = f"{ENDPOINT}/v2/campaigns/{uuid4()}"
    httpx2_mock.head(schedule_url).mock(
        side_effect=[
            MockResponse(codes.NO_CONTENT, headers={"Self": schedule_url}),
            MockResponse(codes.NO_CONTENT, headers={"Self": schedule_url, "Last-Campaign": campaign_url}),
        ]
    )
    oneshot = httpx2_mock.post(f"{schedule_url}/oneshot").respond(codes.ACCEPTED)
    httpx2_mock.head(campaign_url).respond(codes.NO_CONTENT)

    output = invoke_oneshot(
        runner,
        schedule_id,
        "-e",
        "today=datetime(2020, 1, 1)",
        "--expression",
        "flag = x == 1",
        "-e",
        'bands=["g", "r"]',
        "--idempotency-key",
        "abc123",
    )
    assert output["new_campaign_url"] == campaign_url
    request = oneshot.calls.last.request
    assert json.loads(request.content) == {
        "expressions": {"today": "datetime(2020, 1, 1)", "flag": "x == 1", "bands": '["g", "r"]'}
    }
    assert request.headers["Idempotency-Key"] == "abc123"


def test_oneshot_duplicate(
    httpx2_mock: respx.Router, runner: CliRunner, schedule_id: str, schedule_url: str
) -> None:
    """Tests that a reused idempotency key reports the existing campaign."""
    campaign_url = f"{ENDPOINT}/v2/campaigns/{uuid4()}"
    head = httpx2_mock.head(schedule_url).respond(
        codes.NO_CONTENT, headers={"Self": schedule_url, "Last-Campaign": campaign_url}
    )
    httpx2_mock.post(f"{schedule_url}/oneshot").respond(codes.CONFLICT, headers={"Location": campaign_url})

    output = invoke_oneshot(runner, schedule_id, "--idempotency-key", "abc123")
    assert output["new_campaign_url"] == campaign_url
    # The command does not wait for a new campaign
    assert head.call_count == 1


@pytest.mark.parametrize(
    "args,env,expected",
    [
        ([], {}, getuser()),
        (["--user", "ripley"], {}, "ripley"),
        ([], {"CM_USER": "hicks"}, "hicks"),
    ],
    ids=["default", "option", "envvar"],
)
def test_oneshot_actor(
    httpx2_mock: respx.Router,
    runner: CliRunner,
    schedule_id: str,
    schedule_url: str,
    args: list[str],
    env: dict[str, str],
    expected: str,
) -> None:
    """Tests that the request actor is sent to the API."""
    httpx2_mock.head(schedule_url).respond(codes.NO_CONTENT, headers={"Self": schedule_url})
    oneshot = httpx2_mock.post(f"{schedule_url}/oneshot").respond(codes.UNPROCESSABLE_ENTITY)

    runner.invoke(app, [*args, "--endpoint", ENDPOINT, "schedules", "oneshot", schedule_id], env=env)
    assert oneshot.calls.last.request.headers["X-Auth-Request-User"] == expected


@pytest.mark.parametrize("expression", ["today", "=datetime.now()", "today="])
def test_oneshot_bad_expression(runner: CliRunner, schedule_id: str, expression: str) -> None:
    """Tests that malformed expression options are rejected."""
    result = runner.invoke(
        app, ["--endpoint", ENDPOINT, "schedules", "oneshot", schedule_id, "-e", expression]
    )
    assert result.exit_code == 2


def test_refresh(httpx2_mock: respx.Router, runner: CliRunner, schedule_id: str, schedule_url: str) -> None:
    """Tests refreshing a schedule that is changed by its resource."""
    changes = {"cron": {"from": "0 0 * * 0", "to": "0 12 * * *"}}
    refresh = httpx2_mock.post(f"{schedule_url}/refresh").respond(
        codes.OK, json={"changes": changes}, headers={"Self": schedule_url}
    )
    result = runner.invoke(
        app, ["--output", "json", "--endpoint", ENDPOINT, "schedules", "refresh", schedule_id]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"schedule": schedule_url, "changes": changes}
    assert refresh.calls.last.request.headers["X-Auth-Request-User"]

    result = runner.invoke(app, ["--endpoint", ENDPOINT, "schedules", "refresh", schedule_id])
    assert result.exit_code == 0, result.output
    assert "0 12 * * *" in result.output


@pytest.mark.parametrize(
    "status_code,exit_code,output",
    [(codes.NO_CONTENT, 0, "unchanged"), (codes.BAD_GATEWAY, 1, "Could not fetch")],
    ids=["unchanged", "unavailable"],
)
def test_refresh_unchanged_or_failed(
    httpx2_mock: respx.Router,
    runner: CliRunner,
    schedule_id: str,
    schedule_url: str,
    status_code: int,
    exit_code: int,
    output: str,
) -> None:
    """Tests refreshing a schedule that is unchanged, or whose resource cannot
    be used.
    """
    httpx2_mock.post(f"{schedule_url}/refresh").respond(
        status_code, json={"detail": "Could not fetch schedule resource"} if status_code >= 400 else None
    )
    result = runner.invoke(app, ["--endpoint", ENDPOINT, "schedules", "refresh", schedule_id])
    assert result.exit_code == exit_code
    assert output in result.output


# The schedule configuration model's default cron, as normalized by CronStr
DEFAULT_CRON = str(CronStr(ScheduleConfiguration().cron))

CAMPAIGN_MANIFEST = """\
---
apiVersion: io.lsst.cmservice/v1
kind: campaign
metadata:
  name: loaded
spec: {}
"""


def schedule_manifest(spec: str) -> str:
    """Returns a schedule manifest document with the given spec YAML."""
    return f"---\napiVersion: io.lsst.cmservice/v1\nkind: schedule\nmetadata:\n  owner: root\nspec:\n{spec}"


def invoke_load(httpx2_mock: respx.Router, runner: CliRunner, filename: Path) -> tuple[Result, respx.Route]:
    """Invoke the load command with a mocked schedules API, and return its
    result and the API route.
    """
    create = httpx2_mock.post(f"{ENDPOINT}/v2/schedules/").respond(
        codes.CREATED, headers={"Self": f"{ENDPOINT}/v2/schedules/{uuid4()}", "Date": "now"}
    )
    result = runner.invoke(app, ["--endpoint", ENDPOINT, "schedules", "load", str(filename)])
    return result, create


@pytest.mark.parametrize(
    "manifests,expected_cron",
    [
        (CAMPAIGN_MANIFEST + schedule_manifest('  cron: 0 12 * * *\n  name_format: "%s"\n'), "0 12 * * *"),
        (CAMPAIGN_MANIFEST + schedule_manifest('  name_format: "%s"\n'), DEFAULT_CRON),
        (CAMPAIGN_MANIFEST, DEFAULT_CRON),
    ],
    ids=["schedule cron", "no cron", "no schedule manifest"],
)
def test_load_schedule_cron(
    httpx2_mock: respx.Router, runner: CliRunner, tmp_path: Path, manifests: str, expected_cron: str
) -> None:
    """Tests that a loaded schedule's cron is taken from the schedule
    manifest's spec, or else is the schedule configuration model's default,
    and is not part of the schedule's configuration.
    """
    filename = tmp_path / "schedule.yaml"
    filename.write_text(manifests)
    result, create = invoke_load(httpx2_mock, runner, filename)
    assert result.exit_code == 0, result.output
    schedule = json.loads(create.calls.last.request.content)
    assert schedule["cron"] == expected_cron
    assert "cron" not in schedule["configuration"]


@pytest.mark.httpx2(assert_all_called=False)
def test_load_schedule_invalid_cron(httpx2_mock: respx.Router, runner: CliRunner, tmp_path: Path) -> None:
    """Tests that a schedule with an invalid cron is not loaded."""
    filename = tmp_path / "schedule.yaml"
    filename.write_text(CAMPAIGN_MANIFEST + schedule_manifest("  cron: every day\n"))
    result, create = invoke_load(httpx2_mock, runner, filename)
    assert result.exit_code == 1
    assert "Invalid schedule cron" in result.output
    assert not create.called
