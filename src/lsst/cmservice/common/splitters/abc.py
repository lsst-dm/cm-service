from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class Splitter(ABC):
    def __init__(self, *args, **kwargs): ...

    @abstractmethod
    async def split(self) -> AsyncGenerator: ...
