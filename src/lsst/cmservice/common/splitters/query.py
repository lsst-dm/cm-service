from collections.abc import AsyncGenerator

from .abc import Splitter


class QuerySplitter(Splitter):
    """Class implementing a group splitter based on Query split rules."""

    def split(self) -> AsyncGenerator: ...
