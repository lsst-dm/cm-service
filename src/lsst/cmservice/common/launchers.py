"""Module for ABC definitions and helper functions related to WMS or Batch
Systems.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from lsst.cmservice.models.lib.timestamp import element_time


def exponential_retry[**P, T](
    *,
    delay: float | int = 5,
    tries: int = 3,
    backoff: float | int = 1.5,
    retryables: list[str] = [],
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T | None]]]:
    """Decorator factory for applying a retry mechanism to an async function"""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T | None]]:
        """Decorator wraps async function with a retry mechanism"""

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            """Wraps async function with a retry mechanism"""
            evt = asyncio.Event()
            r = None
            _delay = delay
            _tries = tries
            while not evt.is_set():
                try:
                    r = await func(*args, **kwargs)
                    evt.set()
                except Exception as exc:
                    if type(exc).__name__ not in retryables:
                        raise
                    elif _tries < 0:
                        raise
                    else:
                        _delay *= backoff
                        await asyncio.sleep(_delay)
                        _tries -= 1
            return r

        return wrapper

    return decorator


class LauncherCheckResponse(BaseModel):
    """A model describing a response from a Launcher's check method."""

    model_config = ConfigDict(validate_assignment=True)

    success: bool = Field(
        description="A boolean describing whether the check returned a successful result", default=False
    )
    job_id: int | str = Field(description="A job ID relevant to the Launcher type", default=0)
    timestamp: datetime = Field(
        description="The time at which the check occurred or its status was reported",
        default_factory=element_time,
        validate_default=True,
    )
    metadata_: dict = Field(
        description=(
            "A mapping of arbitrary data relevant to the launcher check, to be added to the Node's state"
        ),
        default_factory=dict,
    )

    @field_serializer("timestamp")
    def serialize_datetime(self, dt: datetime) -> int:
        return int(dt.timestamp())


class LaunchManager(ABC):
    """Abstract base class for implementing a Launcher. State machines will use
    a Launcher instance to execute code that interacts with external systems,
    such as submitting work to a batch system or another executor.
    """

    @abstractmethod
    async def launch(self, *args: Any, **kwargs: Any) -> Any: ...

    @abstractmethod
    async def check(self, *args: Any, **kwargs: Any) -> LauncherCheckResponse: ...
