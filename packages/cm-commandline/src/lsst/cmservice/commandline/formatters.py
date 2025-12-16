"""Formatter functions for CM Service CLI"""

from collections.abc import Sequence
from enum import Enum, auto

from rich.table import Table


class Formatters(Enum):
    table = auto()
    json = auto()
    yaml = auto()


def table_builder(o: Sequence[dict], columns: dict[str, str]) -> Table:
    """Outputs a rich table from the `o` sequence of objects, where the spec-
    ified columns (as a mapping of column name, object property) are included.
    """
    table = Table(title="CM Output")

    for column in columns:
        table.add_column(column)
    for row in o:
        column_values = [row.get(v) for _, v in columns.items()]
        table.add_row(*column_values)

    return table


def as_json() -> None: ...


def as_yaml() -> None: ...
