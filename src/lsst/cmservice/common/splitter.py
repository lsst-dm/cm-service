"""Module providing common access to Splitter classes from multiple sub-
modules.
"""

from .enums import SplitterEnum as SplitterEnum
from .splitters.abc import Splitter as Splitter
from .splitters.null import NullSplitter as NullSplitter
from .splitters.query import QuerySplitter as QuerySplitter
from .splitters.values import ValuesSplitter as ValuesSplitter

SplitterMapping: dict[str, type[Splitter]] = {
    "null": NullSplitter,
    "query": QuerySplitter,
    "values": ValuesSplitter,
}
"""A mapping of Node configuration literals to splitter classes."""
