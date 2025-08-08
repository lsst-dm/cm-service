"""Abstract Base Classes used by Stateful Model and/or Machine classes.

These primarily exist and are used to satisfy static type checkers that are
otherwise unaware of any dynamic methods added to Stateful Model classes by
a Machine instance.

Notes
-----
These ABCs were generated automatically by `transitions.experimental.utils.
generate_base_model and simplified and/or modified for use by the application.

These ABCs do not use abstractclasses because the implmentations will not be
available to static type checkers (i.e., they only exist at runtime).

These ABCs may implement methods that are not used by application, i.e., that
involve states that are not referenced by any transition.
"""

from abc import ABC, abstractmethod
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession
from transitions import EventData, Machine
from transitions.extensions.asyncio import AsyncMachine

from ..common.enums import ManifestKind, StatusEnum
from ..db.campaigns_v2 import ActivityLog, Campaign, Node

type AnyStatefulObject = Campaign | Node
type AnyMachine = Machine | AsyncMachine


class StatefulModel(ABC):
    """Base ABC for a Stateful Model, where the Machine will override abstract
    methods and properties when it is created.
    """

    __kind__ = [ManifestKind.other]
    activity_log_entry: ActivityLog | None = None
    db_model: AnyStatefulObject | None
    machine: AnyMachine
    state: StatusEnum
    session: AsyncSession | None = None

    @abstractmethod
    def __init__(
        self, *args: Any, o: AnyStatefulObject, initial_state: StatusEnum = StatusEnum.waiting, **kwargs: Any
    ) -> None: ...

    @abstractmethod
    async def error_handler(self, event: EventData) -> None: ...

    @abstractmethod
    async def prepare_activity_log(self, event: EventData) -> None: ...

    @abstractmethod
    async def update_persistent_status(self, event: EventData) -> None: ...

    @abstractmethod
    async def finalize(self, event: EventData) -> None: ...

    async def may_trigger(self, trigger_name: str) -> bool:
        raise NotImplementedError("Must be overridden by a Machine")

    async def trigger(self, trigger_name: str, **kwargs: Any) -> bool:
        raise NotImplementedError("Must be overridden by a Machine")

    async def resume(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_resume(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def force(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_force(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def pause(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_pause(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def start(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_start(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def unblock(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_unblock(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def unprepare(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_unprepare(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def stop(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_stop(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def retry(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_retry(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_reset(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def reset(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def finish(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_finish(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def block(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_block(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def prepare(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_prepare(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def fail(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_fail(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_overdue(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_overdue(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_overdue(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_failed(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_failed(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_failed(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_rejected(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_rejected(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_rejected(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_blocked(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_blocked(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_blocked(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_paused(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_paused(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_paused(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_rescuable(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_rescuable(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_rescuable(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_waiting(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_waiting(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_waiting(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_ready(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_ready(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_ready(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_prepared(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_prepared(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_prepared(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_running(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_running(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_running(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_reviewable(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_reviewable(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_reviewable(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_accepted(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_accepted(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_accepted(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def is_rescued(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def to_rescued(self) -> bool:
        raise NotImplementedError("This should be overridden")

    async def may_to_rescued(self) -> bool:
        raise NotImplementedError("This should be overridden")
