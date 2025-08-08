"""Module providing common access to Splitter classes from multiple sub-
modules.
"""

from enum import Enum

from .splitters.abc import Splitter as Splitter
from .splitters.null import NullSplitter as NullSplitter
from .splitters.query import QuerySplitter as QuerySplitter
from .splitters.values import ValuesSplitter as ValuesSplitter


class SplitterEnum(Enum):
    """An enumeration of supported splitter kinds where the value is the string
    constant used in the Node configuration.
    """

    NULL = "null"
    QUERY = "query"
    VALUES = "values"


SplitterMapping: dict[str, type[Splitter]] = {
    "null": NullSplitter,
    "query": QuerySplitter,
    "values": ValuesSplitter,
}
"""A mapping of Node configuration literals to splitter classes."""
