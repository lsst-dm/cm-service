import sys
from pathlib import Path
from textwrap import dedent
from time import sleep
from typing import Annotated
from uuid import uuid4

import typer
from httpx import HTTPStatusError, codes
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .. import arguments
from ..client import http_client
from ..models import TypedContext
from . import arguments as schedule_arguments
from . import formatters
from . import lib as schedule_lib

app = typer.Typer()
console = Console()


@app.command(name="create")
def create_schedule(
    ctx: TypedContext,
    *,
    schedule_name: Annotated[str, typer.Argument()],
    cron: schedule_arguments.cron,
    auto_start: Annotated[bool, typer.Option(help="flag scheduled campaigns as running")] = False,
    name_format: Annotated[
        str, typer.Option(help="format string (strftime) used as campaign name prefix")
    ] = "%Y%m%d",
) -> None:
    """Create an empty schedule."""
    raise NotImplementedError


@app.command(name="load")
def load_schedule(
    ctx: TypedContext,
    *,
    filename: Annotated[Path, typer.Argument(file_okay=True, dir_okay=False, exists=True)],
    schedule_name: Annotated[
        str, typer.Argument(help="A schedule name to use instead of any name specified in the file.")
    ] = "",
) -> None:
    """Loads a schedule and its components from a YAML file."""
    manifest_list: list[dict] = schedule_lib.read_schedule_from_file(filename)
    to_load: dict[str, dict] = {}
    schedule = schedule_lib.create_schedule(spec=None)

    # Apply the imported manifests in campaign -> * -> edge order
    for manifest in sorted(
        manifest_list,
        key=lambda m: (m["kind"] == "campaign", m["kind"] != "edge"),
        reverse=True,
    ):
        match manifest["kind"]:
            case "campaign":
                if not schedule_name:
                    campaign_name: str = manifest["metadata"]["name"]
                    schedule_name = f"schedule-{campaign_name}-{uuid4().hex[0:8]}"
                to_load[campaign_name] = manifest
            case "node":
                # Add the imported node to the model's spec and the
                # canvas nodes
                manifest["metadata"].pop("namespace", None)
                node_id = f"{manifest['metadata']['name']}.1"
                to_load[node_id] = manifest
            case "schedule":
                schedule.configuration = manifest["spec"]
            case _:
                manifest["metadata"].pop("namespace", None)
                manifest["metadata"].pop("kind", None)
                if (manifest_id := manifest["metadata"].pop("id", None)) is None:
                    manifest_id = str(uuid4())
                to_load[manifest_id] = manifest

    schedule.name = schedule_name
    schedule = schedule_lib.apply_templates_to_schedule(schedule, to_load)
    # API POST new schedule
    if not (save_result := schedule_lib.post_new_schedule(ctx, schedule)):
        console.print(
            "A problem occurred saving the new schedule. Try again or use export to save an offline copy."
        )
        return None

    headers_dict = dict(save_result.headers)
    headers_dict["name"] = schedule.name
    match formatters.Formatters[ctx.obj.output_format]:
        case formatters.Formatters.table:
            t = formatters.as_table([headers_dict])
            console.print(t)
        case formatters.Formatters.json:
            formatters.as_json(headers_dict)


@app.command(name="oneshot")
def oneshot_schedule(
    ctx: TypedContext,
    schedule: arguments.schedule_id,
) -> None:
    """One-shot a schedule that is not presently enabled."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("[cyan]Starting...", total=None)
        prev_c_url: str | None = None
        new_c_url: str | None = None
        s_url: str | None = None

        with http_client(ctx) as client:
            # Get the last campaign url for the schedule or leave it as none
            # if there is no such header
            try:
                r = client.head(f"/schedules/{schedule}")
                s_url = r.headers["Self"]
                r.raise_for_status()
                prev_c_url = r.headers["Last-Campaign"]
            except KeyError:
                pass

            r = client.post(f"/schedules/{schedule}/oneshot")
            r.raise_for_status()

            # Wait until `timeout` for the schedule to provide a new campaign
            # and for that campaign to not be 404
            timeout = 10.0
            elapsed = 0.0
            while elapsed < timeout:
                try:
                    r = client.head(f"/schedules/{schedule}")
                    r.raise_for_status()
                    new_c_url = r.headers["Last-Campaign"]
                    if new_c_url == prev_c_url:
                        raise ValueError
                except (KeyError, ValueError):
                    sleep(1.0)
                    elapsed += 1.0
                    continue
                try:
                    r = client.head(new_c_url)
                    r.raise_for_status()
                except HTTPStatusError as e:
                    if e.response.status_code == codes.NOT_FOUND:
                        sleep(1.0)
                        elapsed += 1.0
                        continue
                break

    result_dict = {
        "schedule": s_url,
        "previous_campaign_url": prev_c_url,
        "new_campaign_url": new_c_url,
    }
    if elapsed >= timeout:
        console.print(Text("Oneshot Schedule timed out"))
        raise TimeoutError

    match formatters.Formatters[ctx.obj.output_format]:
        case formatters.Formatters.table:
            table = Table(title="CM Schedule Oneshot")
            table.add_column("Name")
            table.add_column("URL")
            for k, v in result_dict.items():
                table.add_row(k, v)
            console.print(table)
        case formatters.Formatters.json:
            formatters.as_json(result_dict)


@app.command(name="audit")
def audit_schedule(
    ctx: TypedContext,
    schedule: arguments.schedule_id,
) -> None:
    """Return an audit of changes to templates belonging to schedule."""

    with http_client(ctx) as client:
        try:
            r = client.get("/audit", params={"object_type": "template", "context.schedule": schedule})
            r.raise_for_status()
            audit: list[dict] = r.json()
        except HTTPStatusError as e:
            console.print(e.response.status_code)
            console.print(e.response.text)
            sys.exit(1)

    if not audit:
        console.print(Panel("[red]No audit logs available for requested schedule[/red]"))
        return None

    for entry in audit:
        console.print(
            Panel(
                dedent(f"""\
            [green]Manifest Template [dark_orange]{entry["object_name"]}[/dark_orange][/green]
            [green]Modified By[/green] [dark_orange]{entry["actor"]}[/dark_orange]
            [green]At[/green] [dark_orange]{entry["created_at"]}[/dark_orange]""")
            )
        )
        syntax = Syntax(entry["context"]["diff"], lexer="diff")
        console.print(syntax)
