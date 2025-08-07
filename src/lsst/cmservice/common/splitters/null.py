from collections.abc import AsyncGenerator

from .abc import Splitter


class NullSplitter(Splitter):
    """Class implementing a group splitter based on Null split rules, i.e.,
    it always generates a single group from an input step.
    """

    async def split(self) -> AsyncGenerator:
        yield "1"
