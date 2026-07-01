"""Formatter functions for CM Service CLI"""

from collections.abc import Sequence
from enum import Enum, auto
from json import dumps

from rich.console import Console
from rich.highlighter import JSONHighlighter
from rich.table import Table

console = Console()


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


def as_json(o: dict) -> None:
    """Print a result dictionary to the console as JSON."""
    pretty = JSONHighlighter()
    json_o = dumps(o)
    if console.is_terminal:
        console.print(pretty(json_o))
    else:
        console.print_json(json_o)


def as_yaml() -> None: ...
