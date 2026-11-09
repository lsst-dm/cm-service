"""Module for classes and functions related to a Kafka event-driven dispatcher.

The dispatcher uses a schedule trigger binding to match schedules to incoming
messages with JMESpath query filters.
"""

import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, cast

import anyio
import jmespath
from confluent_kafka import Message
from jmespath.exceptions import JMESPathError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, select

from lsst.cmservice.models.api.schedules import (
    DispatchHandlerCallableProtocol,
    ScheduleTrigger,
    ScheduleTriggerBinding,
)
from lsst.cmservice.models.db.schedules import Schedule

from ...lib.logging import LOGGER
from ...types import AsyncSession, DatabaseManagerProtocol
from ..models import DispatchContext

KafkaDispatchContext = DispatchContext

logger = LOGGER.bind(module=__name__)


class KafkaDispatcher:
    """Dispatcher class for processing Kafka messages that may be used to
    select, render, and store scheduled template campaigns.
    """

    sessionmaker: async_sessionmaker[AsyncSession] | None
    handler: DispatchHandlerCallableProtocol
    timeout: float = 30.0

    def __init__(self, *args: Any, db_manager: DatabaseManagerProtocol, handler: Any, **kwargs: Any) -> None:
        self.sessionmaker = db_manager.sessionmaker
        self.handler = handler

    async def new_context(self, message: Message) -> AsyncGenerator[KafkaDispatchContext]:
        """Factory for new context objects used by the dispatcher."""
        context = KafkaDispatchContext(sessionmaker=self.sessionmaker, subject=message)
        if context.sessionmaker is None:
            raise RuntimeError("Tried to create a dispatch context without a session factory")
        yield context

    async def dispatch(self, message: Message) -> KafkaDispatchContext:
        """Dispatch the message with a context object for managing database
        sessions and synchronization events.
        """
        context = await anext(self.new_context(message))
        try:
            with anyio.fail_after(self.timeout):
                await self(context)
        except Exception as e:
            context.error = e
        finally:
            context.sessionmaker = None
            context.event.set()
        return context

    async def __call__(self, context: KafkaDispatchContext) -> None:
        """Handle a Kafka message by determining matching scheduled campaigns
        and filtering/transforming the message payload.
        """
        if TYPE_CHECKING:
            assert context.sessionmaker is not None
            assert context.subject is not None
            context.subject = cast(Message, context.subject)

        topic_partition_offset = (
            f"{context.subject.topic()}:{context.subject.partition()}:{context.subject.offset()}"
        )
        async with context.sessionmaker() as session:
            statement = select(Schedule).where(col(Schedule.configuration).contains(context.containment))
            context.target = (await session.exec(statement)).all()
            payload = json.loads(context.subject.value() or b"null")

            # TODO this ought to create a new context for each "target" but the
            # consumer is only aware of a single context from the dispatch
            # method
            for target in context.target:
                session.expunge(target)
                trigger = ScheduleTriggerBinding(**target.configuration.get("trigger", {}))
                try:
                    filter_transform: dict | None = jmespath.search(trigger.protocol, payload)
                    if filter_transform is None:
                        # the "filtering" behavior of the trigger protocol has
                        # not matched this message, so there is no work to do
                        continue
                    elif any([value is None for value in filter_transform.values()]):
                        # the "transform" behavior of the trigger protocol has
                        # not matched the payload; we cannot guarantee correct
                        # behavior
                        logger.warning(
                            "Target schedule protocol does not match payload, skipping message",
                            key=topic_partition_offset,
                            schedule=str(target.id),
                        )
                        continue
                except JMESPathError, AttributeError:
                    logger.exception(
                        "Target schedule has an unprocessable protocol, skipping message",
                        key=topic_partition_offset,
                        schedule=str(target.id),
                    )
                    continue
                else:
                    context.trigger = ScheduleTrigger(
                        source="kafka",
                        actor="daemon",
                        schedule=target.id,
                        key=topic_partition_offset,
                        overrides=filter_transform,
                    )
                await self.dispatch_handler(context)

    async def dispatch_handler(self, context: KafkaDispatchContext) -> None:
        """Handle a message from the dispatcher using the hydrated context
        object.

        The specific handler is part of the context, and is a callable that
        supports the ``DispatchHandlerCallableProtocol``.
        """
        if TYPE_CHECKING:
            assert context.trigger is not None
        try:
            result = await self.handler(schedule_id=context.trigger.schedule, trigger=context.trigger)
            # FIXME result is an enum we may not have access to, but we can
            # establish the contract that 0 = success
            if result.value > 0:
                raise RuntimeError(result)
        except Exception as e:
            context.error = e
