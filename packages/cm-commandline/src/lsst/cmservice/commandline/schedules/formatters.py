"""Formatter functions for CM Service CLI"""

from collections.abc import Sequence

from rich.table import Table

from ..formatters import (
    Formatters as Formatters,
)
from ..formatters import (
    as_json as as_json,
)
from ..formatters import (
    as_yaml as as_yaml,
)


def as_table(o: Sequence) -> Table:
    table = Table(title="CM Schedule")
    table.add_column("Name")
    table.add_column("URL")
    table.add_column("Created At")

    for row in o:
        table.add_row(
            row["name"],
            row["self"],
            row["date"],
        )
    return table
