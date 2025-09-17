from collections.abc import AsyncGenerator

from ..enums import SplitterEnum
from .abc import Splitter


class NullSplitter(Splitter):
    """Class implementing a group splitter based on Null split rules, i.e.,
    it always generates a single group from an input step.
    """

    __kind__ = SplitterEnum.NULL

    async def split(self) -> AsyncGenerator[str, None]:
        """Split method that performs no split logic, and yields a single
        truthy predicate.
        """
        yield "(1=1)"
