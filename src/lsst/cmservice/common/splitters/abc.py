from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import Any

from ..enums import SplitterEnum


class Splitter(ABC):
    """An abstract Splitter class that implements rules for generating Butler
    query predicates for a group.
    """

    __kind__: SplitterEnum

    def __init__(self, *args: Sequence, **kwargs: Mapping[str, Any]): ...

    @abstractmethod
    async def split(self) -> AsyncGenerator[str, Any]:
        """An abstract split method that yields predicate strings."""
        if False:
            yield "TRUE"  # type: ignore[unreachable]
