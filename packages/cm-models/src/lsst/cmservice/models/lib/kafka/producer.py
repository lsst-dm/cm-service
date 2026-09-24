"""A module for defining a Kafka producer object using the Confluent Kafka
package, which is a full-featured Kafka client based on the `rdkafka` library
and supports custom serializers and deserializers.

The Notification producer for this CM application supports minimal custom
producer configuration and defaults to using low-latency parameters including
minimal wait time in the producer buffer, 0 acks, and no expectation of
batching or compression.
"""

from collections.abc import Mapping
from types import TracebackType
from typing import Self

from confluent_kafka import KafkaError, KafkaException, Message, Producer

from ..logging import LOGGER
from .settings import kafka_settings, producer_settings

logger = LOGGER.bind(module=__name__)


class NotificationProducer(Producer):
    """A subclass of a Confluent Kafka Producer optimized for sending CM
    notifications.
    """

    topic: str | None
    key: str | None

    def produce(self, message: bytes) -> None:  # type: ignore[override]
        """Produce a message from provided bytes.

        This method deliberately simplifies the signature of the parent class
        by passing through instance attributes in the place of method params.
        """
        if self.topic is None:
            raise RuntimeError("Producer.topic may not be None")

        try:
            super().produce(
                topic=self.topic,
                value=message,
                key=self.key,
                on_delivery=self.__class__.delivery_cb,
            )
        except KafkaException as e:
            logger.error(e)

        # A non-blocking poll of the producer queue to propogate delivery
        # notifications
        self.poll(0)

    @classmethod
    def delivery_cb(cls, err: KafkaError | None, msg: Message) -> None:
        """A delivery callback function, triggered by the producer library for
        every message.
        """
        if err is not None:
            # TODO what should we do if delivery fails? We can't let it die
            # silently or leave it in a log that no one will see (barring
            # instrumentation).
            logger.warning("Failed to deliver message", err=err)

    @classmethod
    def stats_cb(cls, json_str: str) -> None:
        """A callback method for handling statistics reporting."""
        logger.debug(json_str)

    def shutdown(self) -> None:
        """Called when we are done with the producer."""
        self.flush()

    def __enter__(self) -> Self:
        """Allows use of the producer as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return self.shutdown()


def get_producer(aux: Mapping) -> NotificationProducer:
    """Constructs and returns a configured Kafka producer."""
    _kafka_settings = kafka_settings.model_copy(update=aux)
    _producer_settings = producer_settings.model_copy(update=aux)
    p = NotificationProducer(
        **_producer_settings.model_dump(by_alias=True),
        **_kafka_settings.model_dump(by_alias=True),
        stats_cb=NotificationProducer.stats_cb,
    )
    p.topic = _producer_settings.topic
    p.key = _producer_settings.message_key
    return p
