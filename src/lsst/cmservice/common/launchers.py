"""Module for ABC definitions and helper functions related to WMS or Batch
Systems.
"""

from abc import ABC, abstractmethod
from typing import Any


class LaunchManager(ABC):
    """Abstract base class for implementing a Launcher. State machines will use
    a Launcher instance to execute code that interacts with external systems,
    such as submitting work to a batch system or another executor.
    """

    @abstractmethod
    async def launch(self, *args: Any, **kwargs: Any) -> Any: ...

    @abstractmethod
    async def check(self, *args: Any, **kwargs: Any) -> Any: ...
