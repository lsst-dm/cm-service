"""Formatter functions for CM Service CLI"""

from collections.abc import Sequence

from rich.table import Table

from lsst.cmservice.common.timestamp import iso_timestamp

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
    table = Table(title="CM Manifests")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Version")
    table.add_column("Created At")
    table.add_column("Id")

    for row in o:
        table.add_row(
            row["name"],
            row["kind"],
            str(row["version"]),
            iso_timestamp(row["metadata"]["crtime"]),
            row["id"],
        )
    return table
