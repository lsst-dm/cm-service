"""Module for ABC definitions and helper functions related to WMS or Batch
Systems.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_serializer

from .timestamp import element_time


class LauncherCheckResponse(BaseModel):
    """A model describing a response from a Launcher's check method."""

    class Config:
        validate_assignment = True

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
