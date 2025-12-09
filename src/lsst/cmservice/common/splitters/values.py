from collections.abc import AsyncGenerator, Mapping, Sequence

from ..enums import SplitterEnum
from ..errors import CMInvalidGroupingError
from .abc import Splitter


class ValuesSplitter(Splitter):
    """Class implementing a group splitter based on Values split rules, i.e.,
    given a finite list of scalar values associated with a field, it yields
    one group for each.

    Parameters
    ----------
    dimension : str
        The name of the dimension to use in the predicate

    Values : list[str | int | Sequence[str | int] | Mapping[str, str | int]]
        The set of scalar value descriptors to use in each group-predicate.

    Notes
    -----
    The supported format for a Mapping value is a JSON object that describes
    a range of values with `min`, `max`, and a boolean `endpoint`. If the
    `endpoint` is true, then the range will be a closed interval, otherwise it
    will be a right-open interval.
    """

    __kind__ = SplitterEnum.VALUES

    def __init__(
        self,
        *args: Sequence,
        dimension: str,
        values: list[str | int | Sequence[str | int] | Mapping[str, str | int]],
        **kwargs: Mapping,
    ):
        self.dimension = dimension
        self.values = values

    async def split(self) -> AsyncGenerator[str]:
        """Generates group query predicates based on scalar values for
        dimension ranges. Each value can be a scalar, a sequence, or a range.

        A sequence is described by a list or tuple of direct member values. A
        range is described by a mapping with `min`, `max`, and (optionally)
        `endpoint` keys.
        """
        for value in self.values:
            match value:
                case int():
                    yield f"({self.dimension}={value})"
                case str():
                    yield f"({self.dimension}='{value}')"
                case Mapping():
                    endpoint = value.get("endpoint", False)
                    min_value = value["min"] if isinstance(value["min"], int) else f"""'{value["min"]}'"""
                    max_value = value["max"] if isinstance(value["max"], int) else f"""'{value["max"]}'"""
                    yield (
                        f"({self.dimension} >= {min_value}"
                        f" AND "
                        f"{self.dimension} {'<=' if endpoint else '<'} {max_value})"
                    )
                case Sequence():
                    value_list = ",".join([str(x) for x in value])
                    yield f"({self.dimension} IN ({value_list})"
                case _:
                    raise CMInvalidGroupingError
