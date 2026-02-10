# ruff: noqa: ERA001

import sys
from time import sleep
from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.highlighter import JSONHighlighter
from rich.pretty import pprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from lsst.cmservice.common.timestamp import iso_timestamp
from lsst.cmservice.db.campaigns_v2 import CampaignSummary

from .. import arguments, formatters
from ..client import http_client
from ..loader.app import load_from_yaml
from ..models import TypedContext

app = typer.Typer()
console = Console()


@app.command()
def list(ctx: TypedContext) -> None:
    """list all campaigns"""
    output_format = formatters.Formatters[ctx.obj.output_format]
    with http_client(ctx) as session:
        try:
            r = session.get("/campaigns")
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


@app.command(name="new")
def new_campaign(
    ctx: TypedContext,
    campaign: arguments.campaign_name,
) -> None:
    """Create a new empty campaign"""
    output_format = formatters.Formatters[ctx.obj.output_format]
    data = {
        "apiVersion": "io.lsst.cmservice/v1",
        "kind": "campaign",
        "metadata_": {
            "name": campaign,
        },
        "spec": {},
    }
    with http_client(ctx) as session:
        r = session.post("/campaigns", json=data)
        r.raise_for_status()

    match output_format:
        case formatters.Formatters.table:
            t = formatters.as_table([r.json()])
            Console().print(t)
        case formatters.Formatters.json:
            pretty = JSONHighlighter()
            Console().print(pretty(r.text))
        case formatters.Formatters.yaml:
            print(r)


@app.command(name="describe")
def describe_campaign(
    ctx: TypedContext,
    campaign: arguments.campaign_name,
) -> None:
    """describe a specific campaign"""
    with http_client(ctx) as session:
        r = session.get(f"/campaigns/{ctx.obj.campaign_id}/summary")
        r.raise_for_status()
        # edges_url = r.headers["Edges"]
        # nodes_url = r.headers["Nodes"]
        # campaign_url = r.headers["Self"]

    table = Table(title="CM Campaign")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Owner")
    table.add_column("Count")
    table.add_column("Last Updated")

    campaign_summary = CampaignSummary(**r.json())
    table.add_row(
        campaign_summary.name,
        campaign_summary.status.name,
        campaign_summary.owner,
        None,
        iso_timestamp(campaign_summary.metadata_.get("mtime")),
    )
    table.add_section()

    for node_ in campaign_summary.node_summary:
        table.add_row("Nodes in status", node_.status.name, None, str(node_.count), str(node_.mtime))

    console.print(table)
    # with http_client() as session:
    #     r = session.get(
    #         f"{campaign_url}/graph"
    #     )
    #     r.raise_for_status()
    #     graph: nx.DiGraph = nx.node_link_graph(r.json(), edges="edges")

    # nx.write_network_text(graph, sources=["START"])

    # table = Table(title=f"{campaign_record.name} Nodes")
    # table.add_column("Name")
    # table.add_column("Kind")
    # table.add_column("Status")
    # table.add_column("Last Updated")

    # with http_client() as session:
    #     for g_node in graph.nodes.values():
    #         node_id = g_node["uuid"]
    #         r = session.get(
    #             f"nodes/{node_id}"
    #         )
    #         r.raise_for_status()

    #         node = NodeBase(**r.json())

    #         table.add_row(
    #           node.name,
    #           node.kind.name,
    #           node.status.name,
    #           node.metadata_.get("mtime")
    #         )
    # console.print(table)


@app.command(name="start")
def start_campaign(ctx: TypedContext, campaign: arguments.campaign_name) -> None:
    """start a campaign"""
    data = {"status": "running"}
    status_update_url = None

    with http_client(ctx) as session:
        r = session.patch(
            f"/campaigns/{ctx.obj.campaign_id}",
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
        result_text = Text("Campaign started")
        progress.add_task(description="Starting Campaign...", total=None)
        sleep(5.0)
        with http_client(ctx) as session:
            while True:
                r = session.get(status_update_url)
                if not len(r.json()):
                    sleep(1.0)
                else:
                    break
            activity = r.json()[0]
            if (error := activity.get("detail", {}).get("error")) is not None:
                result_text = Text("Campaign not started")
                result_text.stylize("red")
                pprint(
                    {
                        "error": error,
                        "url": status_update_url,
                    }
                )

        console.print(result_text)


@app.command(name="set")
def set_campaign_status(
    ctx: TypedContext,
    campaign: arguments.campaign_name,
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
    """Change a campaign's status"""
    data = {"status": desired_state, "force": force}
    status_update_url = None

    with http_client(ctx) as session:
        r = session.patch(
            f"/campaigns/{ctx.obj.campaign_id}",
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
        result_text = Text("Campaign updated")
        progress.add_task(description="Updating Campaign...", total=None)
        with http_client(ctx) as session:
            while True:
                r = session.get(status_update_url)
                if not len(r.json()):
                    sleep(5.0)
                else:
                    break
            activity = r.json()[0]
            if (error := activity.get("detail", {}).get("error")) is not None:
                result_text = Text("Campaign not updated")
                result_text.stylize("red")
                pprint(
                    {
                        "error": error,
                        "url": status_update_url,
                    }
                )

        console.print(result_text)


@app.command(name="advance")
def advance_campaign(ctx: TypedContext, campaign: arguments.campaign_name) -> None:
    """advances a paused campaign"""

    status_update_url = None

    with http_client(ctx) as session:
        r = session.post(
            "/rpc/process",
            json={"campaign_id": ctx.obj.campaign_id},
            headers={},
        )
        r.raise_for_status()

        status_update_url = r.headers["StatusUpdate"]

    if not status_update_url:
        return
    else:
        console.print(status_update_url)
        return

    # with Progress(
    #     SpinnerColumn(),
    #     TextColumn("[progress.description]{task.description}"),
    #     transient=True,
    #     console=console,
    # ) as progress:
    #     result_text = Text("Campaign advanced")
    #     progress.add_task(description="Advancing Campaign...", total=None)
    #     with http_client(ctx) as session:
    #         while True:
    #             r = session.get(status_update_url)
    #             if not len(r.json()):
    #                 sleep(10.0)
    #                 progress.add_task(
    #                   description="Advancing Campaign...",
    #                   total=None)
    #             else:
    #                 break
    #         activity = r.json()[0]
    #         if (
    #             error := activity.get("detail", {}).get("error")
    #         ) is not None:
    #             result_text = Text("Campaign not advanced")
    #             result_text.stylize("red")
    #             pprint(
    #                 {
    #                     "error": error,
    #                     "url": status_update_url,
    #                 }
    #             )

    #     console.print(result_text)


@app.command(name="load")
def load_campaign(
    ctx: TypedContext,
    filename: Annotated[
        str,
        typer.Argument(help="A name or path to a YAML file containing a complete set of campaign manifests"),
    ],
    campaign: arguments.campaign_name,
    *,
    auto_run: Annotated[
        bool,
        typer.Option(
            "--start",
            help="Start campaign automatically after loading",
        ),
    ] = False,
) -> None:
    """Loads a campaign from a YAML file, optionally starting it."""

    ctx.invoke(load_from_yaml, ctx=ctx, filename=filename, campaign=campaign, strict=True)

    # If argument "auto-start" is set, try to set campaign status after loading
    if auto_run:
        typer.echo(f"Starting campaign {ctx.obj.campaign_name}")
        ctx.invoke(start_campaign, ctx=ctx, campaign=campaign)
