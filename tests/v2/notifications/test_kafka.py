import asyncio
import json
from collections.abc import Generator, Mapping
from contextlib import AbstractContextManager, nullcontext
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4, uuid5

import pytest
from confluent_kafka import Message
from confluent_kafka.admin import AdminClient
from confluent_kafka.cimpl import NewTopic
from pytest_mock import MockerFixture
from sqlmodel.ext.asyncio.session import AsyncSession
from testcontainers.kafka import KafkaContainer

from lsst.cmservice.config import config
from lsst.cmservice.models.db.campaigns import ActivityLog, Node
from lsst.cmservice.models.db.notifications import NotificationLabel
from lsst.cmservice.models.enums import NotificationLabelEnum, StatusEnum
from lsst.cmservice.models.lib.kafka.consumer import CMConsumer
from lsst.cmservice.models.lib.kafka.models import KafkaNotification
from lsst.cmservice.models.lib.kafka.producer import NotificationProducer, get_producer
from lsst.cmservice.models.lib.kafka.settings import kafka_settings, producer_settings

WAIT_TIME = 5.0
"""How long tests should wait for events, in seconds."""


@pytest.fixture(scope="module")
def kafka_broker(request: pytest.FixtureRequest) -> Generator[str]:
    """Create a Kafka container and yield the bootstrap server address."""

    with KafkaContainer("confluentinc/cp-kafka:7.9.10").with_kraft() as broker:
        yield broker.get_bootstrap_server()


@pytest.fixture(scope="function")
def bootstrap_config(kafka_broker: str) -> Generator[Mapping]:
    """Create test topic and yield an auxilliary configuration for other tests
    and fixtures.
    """

    topic_name = f"cm-output-{str(uuid4())[-8:]}"
    aux = {
        "bootstrap_servers": kafka_broker,
        "security_protocol": "PLAINTEXT",
        "topic": topic_name,
        "topics": [topic_name],
        "group_id": "cmservice",
        "auto_offset_reset": "earliest",
    }
    _kafka_settings = kafka_settings.model_copy(update=aux)
    with AdminClient(_kafka_settings.model_dump(by_alias=True)) as admin:
        futures = admin.create_topics([NewTopic(topic_name, 1, 1)])
        # topic creation is eventually consistent
        for future in futures.values():
            future.result(timeout=WAIT_TIME)
        yield aux
        admin.delete_topics([topic_name])


@pytest.fixture(scope="function")
async def produced_message(mocker: MockerFixture, bootstrap_config: Mapping) -> asyncio.Event:
    """Produce a basic message to the current topic and wait for delivery"""
    message_delivered = asyncio.Event()

    def delivery_cb(err: Exception | None, msg: str | bytes) -> None:
        """set the sentinel event indicating the message has been delivered"""
        assert err is None
        message_delivered.set()

    mocker.patch.object(NotificationProducer, "delivery_cb", new=delivery_cb)
    async with get_producer(bootstrap_config) as producer:
        await producer.aproduce(b"Hello World")

    return message_delivered


@pytest.mark.asyncio(loop_scope="module")
async def test_produce_with_aux_config(
    mocker: MockerFixture,
    bootstrap_config: Mapping,
    produced_message: asyncio.Event,
) -> None:
    """Test that a simple message produced by the NotificationProducer is
    available for a consumer.
    """
    await asyncio.wait_for(produced_message.wait(), timeout=WAIT_TIME)

    message_delivered = asyncio.Event()

    async def message_handler(_: Any, message: Message) -> None:
        """Mock message handler."""
        assert message is not None
        assert message.error() is None
        assert message.value() == b"Hello World"
        message_delivered.set()

    mocker.patch.object(CMConsumer, "default_handler", new=message_handler)
    async with CMConsumer(**bootstrap_config):
        await asyncio.wait_for(message_delivered.wait(), timeout=WAIT_TIME)


@pytest.mark.asyncio(loop_scope="module")
async def test_producer_retries(
    caplog: pytest.LogCaptureFixture, mocker: MockerFixture, bootstrap_config: Mapping
) -> None:
    """Test the retry behavior of the producer"""

    bad_producer = {
        "tries": 2,
        "delay": 0.1,
        "backoff": 1.0,
        "queue_buffering_max_messages": 1,
        "queue_buffering_max_ms": 900_000,
        "message_timeout_ms": 1_800_000,
    }
    for k, v in bad_producer.items():
        mocker.patch.object(producer_settings, k, v)

    bad_producer.update(bootstrap_config)

    # Manufacture a BufferError by producing two messages into a local buffer
    # that only supports one message.
    with caplog.at_level("WARNING"), pytest.raises(BufferError), get_producer(bad_producer) as producer:
        await producer.aproduce(b"Hello World")
        await producer.aproduce(b"Hello World")

    # The log should have one message for each attempt
    log_messages = ["Queue full" in rec.message for rec in caplog.records]
    assert len(log_messages) == 2
    assert all(log_messages)


@pytest.mark.asyncio(loop_scope="module")
async def test_consumer_task(
    mocker: MockerFixture,
    bootstrap_config: Mapping,
    produced_message: asyncio.Event,
) -> None:
    """Test the task form of the CM Consumer."""
    await asyncio.wait_for(produced_message.wait(), timeout=WAIT_TIME)

    shutdown_signal = asyncio.Event()
    message_consumed = asyncio.Event()

    async def message_handler(_: Any, message: Message) -> None:
        """Mock message handler."""
        assert message is not None
        assert message.error() is None
        assert message.value() == b"Hello World"
        message_consumed.set()

    mocker.patch.object(CMConsumer, "default_handler", new=message_handler)

    handles = set()
    async with asyncio.TaskGroup() as tg:
        consumer = CMConsumer(sentinel=shutdown_signal, **bootstrap_config)
        consumer_task = tg.create_task(consumer.task(), name="consumer")
        handles.add(consumer_task)
        await asyncio.wait_for(message_consumed.wait(), timeout=WAIT_TIME)
        shutdown_signal.set()


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize(
    ("filter_value", "cm"),
    [
        (["*:*:accepted"], nullcontext()),
        (["step:running:accepted"], nullcontext()),
        (["*:running:*", "*:*:failed"], nullcontext()),
        (["*:*:failed"], pytest.raises(asyncio.TimeoutError)),
        (["group:running:accepted"], pytest.raises(asyncio.TimeoutError)),
        (["*:ready:*", "*:*:failed"], pytest.raises(asyncio.TimeoutError)),
    ],
    ids=["simple pass", "saturated pass", "compound pass", "simple fail", "saturated fail", "compound fail"],
)
async def test_kafka_notification(
    mocker: MockerFixture,
    filter_value: list[str],
    cm: AbstractContextManager,
    session: AsyncSession,
    test_campaign_groups: str,
    notifications_tg: None,
    bootstrap_config: Mapping,
) -> None:
    """Test notifications using a Kafka transport."""

    assert config.notifications.fernet is not None
    label_name = str(uuid4())[-8:]
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "lambert.1")

    message_delivered = asyncio.Event()
    message_consumed = asyncio.Event()

    # Create a mock delivery callback and patch it in
    def delivery_cb(err: Exception | None, msg: str | bytes) -> None:
        """set the sentinel event indicating the message has been delivered"""
        assert err is None
        message_delivered.set()

    # create a mock consumer message handler and patch it in
    async def message_handler(_: Any, message: Message) -> None:
        """Mock message handler."""
        assert message is not None
        assert message.error() is None
        payload_bytes = message.value()
        assert payload_bytes is not None
        payload: Mapping = json.loads(payload_bytes)
        assert KafkaNotification.model_fields.keys() <= payload.keys()
        message_consumed.set()

    mocker.patch.object(NotificationProducer, "delivery_cb", new=delivery_cb)
    mocker.patch.object(CMConsumer, "default_handler", new=message_handler)

    node = await session.get_one(Node, node_id)
    # create a new notification label with a secret that applies the bootstrap
    # config test fixture
    label = NotificationLabel(
        name=label_name,
        kind=NotificationLabelEnum.kafka,
        configuration={"filters": filter_value},
        secret=config.notifications.fernet.encrypt(json.dumps(bootstrap_config).encode("utf-8")),
    )
    session.add(label)
    await session.commit()

    # create a new activity log
    activity = ActivityLog(
        namespace=node.campaign.id,
        node=node.id,
        operator="test",
        from_status=StatusEnum.running,
        to_status=StatusEnum.accepted,
        detail={},
        metadata_={},
        notification_labels=[label_name],
    )
    session.add(activity)
    await session.commit()

    async with CMConsumer(**bootstrap_config):
        with cm:
            await asyncio.wait_for(message_delivered.wait(), timeout=WAIT_TIME)
            await asyncio.wait_for(message_consumed.wait(), timeout=WAIT_TIME)
