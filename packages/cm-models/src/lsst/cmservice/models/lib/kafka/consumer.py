"""Implement a Kafka consumer.

A CM Service may operate one or more Kafka consumers. Each consumer may
subscribe to one or more topics. A message consumed from a topic may cause the
creation of a new campaign or used as a trigger for a templated campaign,
depending on the business logic applied in a handler function.

Consuming Messages
------------------
CM Service operates Kafka consumers using a single group id, as configured in
application-level consumer settings via the environment variable
``KAFKA_CONSUMER_GROUP_ID``.

It is the policy of CM Service that consumed messages are not auto-committed.
The topic-partition and offset of any message used to create, update, or
trigger a campaign operation should be added to the ``metadata`` of that
campaign for reference.
Offsets should only be commited by the consumer once the handler operation has
completed successfully (or has failed such that retrying is futile).

Offsets for futile messages are committed to avoid poison-pill consumer
blockages and may be republished to a DLQ topic if one is available.

Topic-Handlers
--------------
CM Service assumes that all messages available in a topic are appropriately
handled by a single handler function, and that each subscribed topic has an
associated handler.

The Kafka consumer places messages as they are received onto a "receive queue",
which is an `anyio` memory object stream.
"""

from contextlib import AsyncExitStack
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

import anyio
from anyio import to_thread
from anyio.lowlevel import checkpoint
from confluent_kafka import Consumer, KafkaError, Message, TopicPartition

from ..logging import LOGGER
from .settings import consumer_settings, kafka_settings

if TYPE_CHECKING:
    from anyio.abc._tasks import TaskGroup
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from fastapi import FastAPI

logger = LOGGER.bind(module=__name__)


class CMConsumer(Consumer):
    """Campaign Management Kafka consumer.

    This consumer implements an asynchronous consumer based on the
    ``confluent_kafka.Consumer``. The main feature added to the consumer is an
    asynchronous context manager that when entered performs a (blocking) topic
    subscription based on the instance's `topics` attribute. This context
    manager also starts an ``anyio`` task group with a perpetual consumer loop
    in one task and a message handler dispatch task in another, linkeed by
    ``anyio``'s memory object streams (a queue-like synchronization primitive).

    There are three ways to use this consumer:

    1. As a normal ``confluent_kafka.Consumer``, with manual topic assignment
       and handling, including as a context manager.
    2. As an async context manager, with automatic topic assignment and
       handling.
    3. As a task, by calling the ``task()`` method on a CMConsumer instance
       to run the consumer until an optional sentinel event is set to indicate
       shutdown.

    When using methods 2 or 3, a sentinel event is used to indicate that the
    consumer should continue polling for messages. When this event is set, the
    poller sub-task will no longer poll, and if used, the `task` form of the
    consumer is ended.

    Parameters
    ----------
    app: ``FastAPI`` | ``None``
        A reference to a ``FastAPI`` application instance, if the consumer is
        operating as part of one.
    sentinel: ``anyio.Event`` | None
        An external sentinel event the instance should use as a teardown signal
        when the application is shutting down. If not supplied, a default
        internal event is used.
    topics : ``list`` [``str``]
        A list of topic names to which the consumer should subscribe.
    """

    app: FastAPI | None
    assigned: anyio.Event
    sentinel: anyio.Event
    topics: list[str] | None
    poll_wait: float
    _exit_stack: AsyncExitStack
    _receive_stream: MemoryObjectReceiveStream[Message]
    _send_stream: MemoryObjectSendStream[Message]
    _task_group: TaskGroup | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a new instance of a consumer."""

        if "sentinel" in kwargs:
            self.sentinel = kwargs.pop("sentinel")
        else:
            self.sentinel = anyio.Event()
        self.app: FastAPI | None = kwargs.pop("app", None)
        self._exit_stack = AsyncExitStack()
        self._task_group = None
        _consumer_settings = consumer_settings.model_copy(update=kwargs)
        _kafka_settings = kafka_settings.model_copy(update=kwargs)
        super().__init__(
            *args,
            **_kafka_settings.model_dump(by_alias=True),
            **_consumer_settings.model_dump(by_alias=True),
        )
        self.topics = _consumer_settings.topics
        self.poll_wait = _consumer_settings.max_poll_wait_sec
        self.assigned = anyio.Event()
        self._send_stream, self._receive_stream = anyio.create_memory_object_stream[Message](
            _consumer_settings.max_send_queue_size
        )

    async def __aenter__(self) -> Self:
        """Allows use of the consumer as an async context manager.

        When the context is entered, the consumer subscribes to its list of
        topics and waits for assignment.
        """
        if self.topics is None:
            raise RuntimeError("Consumer must be assigned topics")

        self.subscribe(self.topics, on_assign=self.on_assign, on_revoke=self.on_revoke, on_lost=self.on_lost)
        while not self.assigned.is_set():
            message = await to_thread.run_sync(self.poll, self.poll_wait)
            if message is None:
                await checkpoint()
                continue
            if (kafka_error := message.error()) is not None:
                match kafka_error.code():
                    case KafkaError.UNKNOWN_TOPIC_OR_PART:
                        # If the topic has not been created yet, it may
                        # become eventually consistent, or we could be
                        # trying to subscribe to the wrong topic and
                        # this will never resolve.
                        # TODO this is probably fatal in real life
                        logger.warning("Kafka consumer reports unknown topic-partition", topics=self.topics)
                        await checkpoint()
                        continue
                    case _ as e:
                        raise RuntimeError("Kafka consumer failed to subscribe: %s", e)
            else:
                await self._send_stream.send(message)

        await self._exit_stack.__aenter__()
        try:
            self._task_group = await self._exit_stack.enter_async_context(anyio.create_task_group())
            self._task_group.start_soon(self.consume_loop, self._send_stream)
            self._task_group.start_soon(self.message_dispatch, self._receive_stream)
            logger.info("Started consumer and handler tasks")
            return self
        except Exception:
            await self._exit_stack.aclose()
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager. Set the shutdown sentinel if it is
        not set and close the consumer.
        """
        self.sentinel.set()
        await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)
        await to_thread.run_sync(self.close)

    async def task(self) -> None:
        """A coro that is meant to be used with `asyncio.create_task` to
        establish and maintain a perpetual reference to the consumer under-
        lying this class instance until a shutdown event is set.
        """
        async with self:
            logger.info("Started consumer")
            await self.sentinel.wait()
            logger.info("Consumer is shutting down")

    async def consume_loop(self, stream: MemoryObjectSendStream) -> None:
        """Task establishing a Kafka consumer loop, which adds polled messages
        to the consumer's memory object stream.
        """
        async with stream:
            while not self.sentinel.is_set():
                message = await to_thread.run_sync(self.poll, self.poll_wait)
                if message is None:
                    await checkpoint()
                elif kafka_error := message.error():
                    # A consumer can be configured to receive a partition EOF
                    # event, which is provided as an error.
                    if kafka_error.code() == KafkaError._PARTITION_EOF:
                        await self.on_eof(message)
                    else:
                        await self.on_error(kafka_error)
                else:
                    await stream.send(message)

    async def message_dispatch(self, stream: MemoryObjectReceiveStream[Message]) -> None:
        """Task establishing a Message dispatcher, handles messages that are
        enqueued by the consumer poll loop and passed to handlers based on an
        available topic-handler mapping, or the default handler.
        """
        async with stream:
            async for message in stream:
                match message.topic:
                    case _:
                        await self.default_handler(message)

    async def default_handler(self, message: Message) -> None:
        """Default message handler commits message without any particular
        handling.
        """
        self.commit(message=message, asynchronous=True)

    def on_assign(self, consumer: Consumer, topic_partitions: list[TopicPartition]) -> None:
        """Subscription assignment callback method.

        This may be invoked during initial assignment following a subscription,
        or periodically during rebalance operations.
        """
        logger.info("Consumer received subscription assignment", topic_partitions=topic_partitions)
        self.assigned.set()

    def on_revoke(self, consumer: Consumer, topic_partitions: list[TopicPartition]) -> None:
        """Subscription assignment revocation callback method."""
        logger.info("Consumer received subscription revocation", topic_partitions=topic_partitions)

    def on_lost(self, consumer: Consumer, topic_partitions: list[TopicPartition]) -> None:
        """Callback for lost partition assignment."""
        logger.info("Consumer has lost partition assignment", topic_partitions=topic_partitions)

    async def on_eof(self, message: Message) -> None:
        """Callback for partition EOF events. This is a no-op."""
        logger.info(
            "Consumer reached EOF on a topic-partition", topic=message.topic, partition=message.partition
        )
        await checkpoint()

    async def on_error(self, kafka_error: KafkaError) -> None:
        """Callback for error events."""
        logger.error("Consumer received an error message", kafka_error=kafka_error.name())
        await checkpoint()
