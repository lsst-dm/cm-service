"""Module defining models and ABCs for trigger components."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from types import TracebackType

from anyio import Event
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..api.schedules import ScheduleTrigger
from ..db.schedules import Schedule
from ..types import AsyncSession, ScheduleTriggerSubjectProtocol


@dataclass
class DispatchContext:
    """Dataclass defining a context object for a dispatch mechanism.

    The dispatch context preserves the context of a triggering action in terms
    of "subject -> [triggers] -> target".

    Attributes
    ----------
    error
        An exception or traceback as an error raised in the handler.
    event
        A synchronization event shared by the dispatcher and its caller.
    sessionmaker: ``async_sessionmaker`` [ ``AsyncSession`` ]
        An async session factory that will provide a database session to the
        handler.
    subject
        The event or message object received by a dispatcher.
    target
        The object of the triggering action, such as a scheduled campaign.
    trigger
        A ``ScheduleTrigger`` object constructed with any overrides transformed
        from the subject payload.
    """

    error: BaseException | TracebackType | None = None
    event: Event = field(default_factory=Event)
    trigger: ScheduleTrigger | None = None
    sessionmaker: async_sessionmaker[AsyncSession] | None = None
    subject: ScheduleTriggerSubjectProtocol | None = None
    target: Sequence[Schedule] = field(default_factory=list)

    @property
    def containment(self) -> dict:
        if self.subject is None:
            return {}
        return {"trigger": {"source": "kafka", "channel": self.subject.topic()}}
