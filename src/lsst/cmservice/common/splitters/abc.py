from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import Any


class Splitter(ABC):
    def __init__(self, *args: Sequence, **kwargs: Mapping[str, Any]): ...

    @abstractmethod
    async def split(self) -> AsyncGenerator[str, Any]:
        if False:
            yield "1"  # type: ignore[unreachable]
