"""Formatter functions for CM Service CLI"""

from collections.abc import Sequence
from enum import Enum, auto

from rich.table import Table


class Formatters(Enum):
    table = auto()
    json = auto()
    yaml = auto()


def as_table(o: Sequence) -> Table:
    table = Table(title="CM Output")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Owner")

    for row in o:
        table.add_row(row["name"], row["status"], row["owner"])
    return table


def as_json() -> None: ...


def as_yaml() -> None: ...
