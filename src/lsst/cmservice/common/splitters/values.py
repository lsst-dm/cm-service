from collections.abc import AsyncGenerator, Mapping, Sequence

from .abc import Splitter


class ValuesSplitter(Splitter):
    """Class implementing a group splitter based on Values split rules, i.e.,
    given a finite list of scalar values associated with a field, it yields
    one group for each.

    Parameters
    ----------
    field : str
        The name of the field to use in the predicate

    Values : list[str | int]
        The set of scalar values to use in each group-predicate.
    """

    def __init__(self, *args: Sequence, field: str, values: list[str | int], **kwargs: Mapping):
        self.field = field
        self.values = values

    async def split(self) -> AsyncGenerator[str, None]:
        """Generates group query predicates based on a single scalar value for
        a field.
        """
        for value in self.values:
            yield f"{self.field} in ({value})"
