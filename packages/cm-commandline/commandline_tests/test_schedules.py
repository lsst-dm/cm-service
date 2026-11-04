"""Tests for the schedules commands"""

import json
from getpass import getuser
from uuid import uuid4

import pytest
import respx

# respx mocks the httpx2 transport but builds responses as httpx responses
# FIXME refactor with httpx2 when respx (or a replacement) supports it
from httpx import Response as MockResponse
from httpx2 import codes
from typer.testing import CliRunner

from lsst.cmservice.commandline.cli import app

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
