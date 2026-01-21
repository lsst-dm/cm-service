from time import sleep
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from .. import arguments
from ..client import http_client
from ..models import TypedContext

app = typer.Typer()
console = Console()


@app.command(name="set")
def set_node_status(
    ctx: TypedContext,
    node: arguments.node_id,
    desired_state: arguments.campaign_status,
    *,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Request unconditonal status update",
        ),
    ] = False,
) -> None:
    """Change a node's status"""
    data = {"status": desired_state, "force": force}
    status_update_url = None

    with http_client(ctx) as session:
        r = session.patch(
            f"/nodes/{node}",
            json=data,
            headers={"Content-Type": "application/merge-patch+json"},
        )
        r.raise_for_status()

        status_update_url = r.headers["StatusUpdate"]

    if not status_update_url:
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        result_text = Text("Node updated")
        progress.add_task(description="Updating Node...", total=None)
        with http_client(ctx) as session:
            while True:
                r = session.get(status_update_url)
                r.raise_for_status()
                if not len(r.json()):
                    sleep(5.0)
                else:
                    break
            activity = r.json()[0]
            if (error := activity.get("detail", {}).get("error")) is not None:
                result_text = Text("Node not updated")
                result_text.stylize("red")
                typer.echo(
                    {
                        "error": error,
                        "url": status_update_url,
                    },
                    err=True,
                )

        console.print(result_text)
