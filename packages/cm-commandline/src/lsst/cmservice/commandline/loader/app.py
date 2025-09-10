from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .loader import load_selected_file

app = typer.Typer()


@app.command(name="yaml")
def load_from_yaml(
    ctx: typer.Context,
    filename: str,
    campaign_name: Annotated[str | None, typer.Argument(envvar="CM_CAMPAIGN")] = None,
) -> None:
    """Load manifests from a YAML file"""
    headers = load_selected_file(ctx, Path(filename), campaign_name)

    if headers:
        table = Table(title=campaign_name)
        table.add_column("Link Name")
        table.add_column("Link")

        for k, v in headers.items():
            table.add_row(k, v)

        Console().print(table)
