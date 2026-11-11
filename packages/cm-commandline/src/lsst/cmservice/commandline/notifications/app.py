import json
from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.highlighter import JSONHighlighter

from ..models import TypedContext
from . import formatters, lib

app = typer.Typer()
console = Console()


@app.command(name="list")
def list(
    ctx: TypedContext,
) -> None:
    """List current notification labels"""
    output_format = formatters.Formatters[ctx.obj.output_format]

    labels = lib.list_notification_labels(ctx)

    match output_format:
        case formatters.Formatters.table:
            t = formatters.as_table(labels)
            Console().print(t)
        case formatters.Formatters.json:
            pretty = JSONHighlighter()
            Console().print(pretty(json.dumps(labels)))
        case formatters.Formatters.yaml:
            print(json.dumps(labels))


@app.command(name="delete")
def delete(
    ctx: TypedContext,
    label_name: Annotated[str, typer.Argument()],
) -> None:
    """Delete a notification label"""
    lib.delete_notification_labels(ctx, label_name)
