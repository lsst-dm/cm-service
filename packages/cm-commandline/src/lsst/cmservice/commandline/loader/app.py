from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .. import arguments
from ..models import TypedContext
from .loader import StrictModeViolationError, load_selected_file

app = typer.Typer()


@app.command(name="yaml")
def load_from_yaml(
    ctx: TypedContext,
    filename: str,
    campaign: arguments.campaign_name,
    *,
    strict: Annotated[
        bool, typer.Option(help="Load YAML in strict mode (file must have only a single campaign)")
    ] = False,
) -> None:
    """Load manifests from a YAML file"""
    try:
        headers = load_selected_file(ctx, yaml_file=Path(filename), campaign=campaign, strict=strict)
    except StrictModeViolationError as e:
        typer.echo(e, err=True)
        raise typer.Exit(1)

    if headers:
        table = Table(title=ctx.obj.campaign_name)
        table.add_column("Link Name")
        table.add_column("Link")

        for k, v in headers.items():
            table.add_row(k, v)

        Console().print(table)
