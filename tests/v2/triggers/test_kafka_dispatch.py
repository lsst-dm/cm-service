from functools import partial
from textwrap import dedent
from uuid import uuid4

import pytest
import pytest_asyncio
from confluent_kafka import Message
from httpx2 import AsyncClient, codes
from pytest_mock import MockerFixture

from lsst.cmservice.common.daemon_v2 import daemon_scheduled_job
from lsst.cmservice.db.session import DatabaseManager
from lsst.cmservice.models.triggers.dispatchers import kafka


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def target_schedule(aclient: AsyncClient) -> str:
    """Create a schedule with a kafka trigger"""
    test_case = {
        "name": f"schedule_{uuid4().hex[:8]}",
        "cron": "0 */4 * * WED",
        "configuration": {
            "expressions": {
                "today": "datetime.now()",
            },
            "trigger": {
                "source": "kafka",
                "channel": "test-topic",
                "protocol": "(type=='test' && state=='complete') && {today: detail.day_obs} || `null`",
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
                    spec:
                        today: '${{ today }}'
                """),
            },
        ],
    }
    x = await aclient.post("/v2/schedules", json=test_case)
    assert x.status_code == codes.CREATED
    return x.headers["self"]


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def target_schedule_bad_protocol(aclient: AsyncClient) -> str:
    """Create a schedule with a kafka trigger"""
    test_case = {
        "name": f"schedule_{uuid4().hex[:8]}",
        "cron": "0 */4 * * WED",
        "configuration": {
            "expressions": {
                "today": "datetime.now()",
            },
            "trigger": {
                "source": "kafka",
                "channel": "test-topic",
                "protocol": "(type=='test' && state=='complete) && {today: detail.day_obs} || `null`",
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
                    spec:
                        today: '${{ today }}'
                """),
            },
        ],
    }
    x = await aclient.post("/v2/schedules", json=test_case)
    assert x.status_code == codes.CREATED
    return x.headers["self"]


@pytest.mark.parametrize(
    "message_value,creates_campaign,expected_error",
    [
        (b'{"type": "test", "state": "complete", "detail": {"day_obs": 20260314}}', True, None),
        (b'{"type": "test", "state": "failed", "detail": {"day_obs": 20260314}}', False, None),
        (b'{"type": "test", "state": "complete", "detail": {"day_obs": 20260314,}', False, "JSONDecodeError"),
    ],
    ids=["good message yes", "good message no", "bad message json"],
)
async def test_kafka_dispatch_handler(
    *,
    testdb: DatabaseManager,
    target_schedule: str,
    aclient: AsyncClient,
    message_value: bytes,
    creates_campaign: bool,
    expected_error: str | None,
) -> None:
    """Test the Kafka dispatch mechanism with a mock message resulting in a
    successful rendered campaign.
    """
    message = Message(
        topic="test-topic",
        partition=0,
        offset=0,
        value=message_value,
    )

    # The daemon startup builds a callable for the message handler
    handler = partial(
        daemon_scheduled_job,
        suppress_exceptions=False,
        oneshot=True,
    )

    # The daemon startup creates a dispatcher for the consumer to use
    dispatcher = kafka.KafkaDispatcher(db_manager=testdb, handler=handler)

    # The consumer calls the dispatch method of a configured dispatcher
    context = await dispatcher.dispatch(message=message)

    assert context.event.is_set()

    match expected_error:
        case None:
            assert context.error is None
        case str():
            assert context.error is not None
            assert expected_error in f"{context.error.__class__}: {context.error}"

    x = await aclient.get(target_schedule)
    assert x.status_code == codes.OK
    schedule = x.json()

    campaign_id = schedule[0]["metadata"].get("last_campaign_id", None)
    if creates_campaign:
        x = await aclient.get(f"v2/campaigns/{campaign_id}")
        assert x.status_code == codes.OK
        campaign = x.json()
        assert campaign["configuration"]["today"] == "20260314"
    else:
        assert campaign_id is None


@pytest.mark.parametrize(
    "message_value,creates_campaign,expected_error",
    [
        (
            b'{"type": "test", "state": "complete", "detail": {"day_obs": 20260314}}',
            False,
            "LexerError: Bad jmespath expression",
        ),
    ],
    ids=["good message bad protocol"],
)
async def test_kafka_dispatch_handler_bad_protocol(
    *,
    caplog: pytest.LogCaptureFixture,
    testdb: DatabaseManager,
    target_schedule_bad_protocol: str,
    aclient: AsyncClient,
    message_value: bytes,
    creates_campaign: bool,
    expected_error: str | None,
) -> None:
    """Test the Kafka dispatch mechanism with a mock message against a bad
    protocol; no campaign is created and an error is logged.
    """
    message = Message(
        topic="test-topic",
        partition=0,
        offset=0,
        value=message_value,
    )

    # The daemon startup builds a callable for the message handler
    handler = partial(
        daemon_scheduled_job,
        suppress_exceptions=False,
        oneshot=True,
    )

    # The daemon startup creates a dispatcher for the consumer to use
    dispatcher = kafka.KafkaDispatcher(db_manager=testdb, handler=handler)

    # The consumer calls the dispatch method of a configured dispatcher
    context = await dispatcher.dispatch(message=message)

    assert context.event.is_set()

    match expected_error:
        case None:
            assert context.error is None
        case str():
            assert context.error is None
            assert expected_error in caplog.text

    x = await aclient.get(target_schedule_bad_protocol)
    assert x.status_code == codes.OK
    schedule = x.json()

    campaign_id = schedule[0]["metadata"].get("last_campaign_id", None)
    if creates_campaign:
        x = await aclient.get(f"v2/campaigns/{campaign_id}")
        assert x.status_code == codes.OK
        campaign = x.json()
        assert campaign["configuration"]["today"] == "20260314"
    else:
        assert campaign_id is None


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def target_schedule_enabled(aclient: AsyncClient) -> str:
    """Create an enabled schedule with a kafka trigger"""
    test_case = {
        "name": f"schedule_{uuid4().hex[:8]}",
        "cron": "0 */4 * * WED",
        "is_enabled": True,
        "configuration": {
            "expressions": {
                "today": "datetime.now()",
            },
            "trigger": {
                "source": "kafka",
                "channel": "test-topic",
                "protocol": "(type=='test' && state=='complete') && {today: detail.day_obs} || `null`",
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
                    spec:
                        today: '${{ today }}'
                """),
            },
        ],
    }
    x = await aclient.post("/v2/schedules", json=test_case)
    assert x.status_code == codes.CREATED
    return x.headers["self"]


async def test_kafka_dispatch_skips_enabled_schedule(
    *,
    caplog: pytest.LogCaptureFixture,
    mocker: MockerFixture,
    testdb: DatabaseManager,
    target_schedule_enabled: str,
    aclient: AsyncClient,
) -> None:
    """Test that the Kafka dispatch mechanism does not trigger an enabled
    schedule, even when a message matches its trigger binding.
    """
    message = Message(
        topic="test-topic",
        partition=0,
        offset=0,
        value=b'{"type": "test", "state": "complete", "detail": {"day_obs": 20260314}}',
    )

    handler = mocker.AsyncMock()
    dispatcher = kafka.KafkaDispatcher(db_manager=testdb, handler=handler)
    context = await dispatcher.dispatch(message=message)

    assert context.event.is_set()
    assert context.error is None
    assert context.target == []
    handler.assert_not_awaited()
    assert "Enabled schedule has a trigger binding" in caplog.text

    x = await aclient.get(target_schedule_enabled)
    assert x.status_code == codes.OK
    schedule = x.json()
    assert schedule[0]["is_enabled"] is True
    assert schedule[0]["metadata"].get("last_campaign_id", None) is None
