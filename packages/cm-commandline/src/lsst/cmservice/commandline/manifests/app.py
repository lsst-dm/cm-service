import sys
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.highlighter import JSONHighlighter

from ..client import http_client
from . import formatters

app = typer.Typer()
console = Console()


@app.command()
def list(ctx: typer.Context) -> None:
    """list all manifests"""
    output_format = formatters.Formatters[ctx.obj.get("output_format")]
    with http_client(ctx) as session:
        try:
            r = session.get("/manifests")
            r.raise_for_status()
        except Exception as e:
            print(e)
            sys.exit(1)

    match output_format:
        case formatters.Formatters.table:
            t = formatters.as_table(r.json())
            Console().print(t)
        case formatters.Formatters.json:
            pretty = JSONHighlighter()
            Console().print(pretty(r.text))
        case formatters.Formatters.yaml:
            print(r.text)


@app.command(name="describe")
def describe_manifest(ctx: typer.Context, manifest_id: Annotated[str, typer.Argument(parser=UUID)]) -> None:
    """Describes a manifest by listing its versions"""
    with http_client(ctx) as session:
        try:
            r = session.get(f"/manifests/{manifest_id}")
            r.raise_for_status()
        except Exception as e:
            print(e)
            sys.exit(1)

    match formatters.Formatters[ctx.obj.get("output_format")]:
        case formatters.Formatters.table:
            t = formatters.as_table([r.json()])
            Console().print(t)
            Console().print(r.json()["spec"])
        case formatters.Formatters.json:
            pretty = JSONHighlighter()
            Console().print(pretty(r.text))
        case formatters.Formatters.yaml:
            print(r.text)
