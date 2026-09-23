import asyncio
import json
import time
from collections.abc import Generator, Mapping
from contextlib import AbstractContextManager, nullcontext
from urllib.parse import urlparse
from uuid import UUID, uuid4, uuid5

import pytest
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient
from confluent_kafka.cimpl import NewTopic
from pytest_mock import MockerFixture
from sqlmodel.ext.asyncio.session import AsyncSession
from testcontainers.kafka import KafkaContainer

from lsst.cmservice.config import config
from lsst.cmservice.models.db.campaigns import ActivityLog, Node
from lsst.cmservice.models.db.notifications import NotificationLabel
from lsst.cmservice.models.enums import NotificationLabelEnum, StatusEnum
from lsst.cmservice.models.lib.kafka.models import KafkaNotification
from lsst.cmservice.models.lib.kafka.producer import NotificationProducer, get_producer
from lsst.cmservice.models.lib.kafka.settings import consumer_settings, kafka_settings


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
    }
    _kafka_settings = kafka_settings.model_copy(update=aux)
    with AdminClient(_kafka_settings.model_dump(by_alias=True)) as admin:
        admin.create_topics([NewTopic(topic_name, 1, 1)])
        yield aux
        admin.delete_topics([topic_name])


@pytest.fixture(scope="function")
def consumer(bootstrap_config: Mapping) -> Generator[Consumer]:
    """Yield a consumer configured for the test environment."""

    _consumer_settings = consumer_settings.model_copy(update=bootstrap_config)
    _kafka_settings = kafka_settings.model_copy(update=bootstrap_config)
    with Consumer(
        **_consumer_settings.model_dump(by_alias=True), **_kafka_settings.model_dump(by_alias=True)
    ) as consumer:
        consumer.subscribe(_consumer_settings.topics)
        assignment_deadline = time.monotonic() + 5
        while not consumer.assignment():
            if time.monotonic() >= assignment_deadline:
                raise TimeoutError("Consumer has not been assigned a TopicPartition")
            consumer.poll(0.1)
        yield consumer
        consumer.unsubscribe()


def test_produce_with_aux_config(bootstrap_config: Mapping, consumer: Consumer) -> None:
    """Test that a simple message produced by the NotificationProducer is
    available for a consumer.
    """

    with get_producer(bootstrap_config) as producer:
        producer.produce(b"Hello World")

    message = consumer.poll(5.0)
    assert message is not None
    assert message.error() is None
    assert message.value() == b"Hello World"


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
    consumer: Consumer,
) -> None:
    """Test notifications using a Kafka transport."""

    assert config.notifications.fernet is not None
    label_name = str(uuid4())[-8:]
    message_delivered = asyncio.Event()
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "lambert.1")

    # Create a mock delivery callback and patch it in
    def delivery_cb(err: Exception | None, msg: str | bytes) -> None:
        """set the sentinel event indicating the message has been delivered"""
        assert err is None
        message_delivered.set()

    mocker.patch.object(NotificationProducer, "delivery_cb", new=delivery_cb)

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

    with cm:
        await asyncio.wait_for(message_delivered.wait(), timeout=5.0)

        # use a consumer to validate the receipt of the notification message
        message = consumer.poll(5.0)
        assert message is not None
        assert message.error() is None
        payload_bytes = message.value()
        assert payload_bytes is not None
        payload: Mapping = json.loads(payload_bytes)
        assert KafkaNotification.model_fields.keys() <= payload.keys()
