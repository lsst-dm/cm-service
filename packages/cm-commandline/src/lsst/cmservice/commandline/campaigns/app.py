# ruff: noqa: ERA001

import sys
from time import sleep
from typing import Annotated

import typer
from httpx2 import HTTPError, codes
from rich import print
from rich.console import Console
from rich.highlighter import JSONHighlighter
from rich.pretty import pprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from lsst.cmservice.models.db.campaigns import CampaignSummary
from lsst.cmservice.models.lib.timestamp import iso_timestamp

from .. import arguments, formatters, options
from ..client import http_client
from ..loader.app import load_from_yaml
from ..models import TypedContext
from .formatters import as_audit_table

app = typer.Typer()
console = Console()


@app.command()
def list(ctx: TypedContext, *, limit: options.limit = 10) -> None:
    """list campaigns"""
    output_format = formatters.Formatters[ctx.obj.output_format]
    with http_client(ctx) as client:
        try:
            r = client.get("/campaigns/", params={"limit": limit})
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
    campaign: arguments.CampaignName.Required,
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
    with http_client(ctx) as client:
        r = client.post("/campaigns/", json=data)
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
    campaign: arguments.CampaignName.Required,
) -> None:
    """describe a specific campaign"""
    with http_client(ctx) as client:
        r = client.get(f"/campaigns/{ctx.obj.campaign_id}/summary")
        r.raise_for_status()
        # edges_url = r.headers["Edges"]
        # nodes_url = r.headers["Nodes"]
        # campaign_url = r.headers["Self"]

    campaign_summary = CampaignSummary(**r.json())

    table = Table(title="CM Campaign", caption=str(campaign_summary.id))
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Owner")
    table.add_column("Count")
    table.add_column("Last Updated")

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
    # with http_client() as client:
    #     r = client.get(
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

    # with http_client() as client:
    #     for g_node in graph.nodes.values():
    #         node_id = g_node["uuid"]
    #         r = client.get(
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
def start_campaign(ctx: TypedContext, campaign: arguments.CampaignName.Required) -> None:
    """start a campaign"""
    data = {"status": "running"}
    status_update_url = None

    with http_client(ctx) as client:
        r = client.patch(
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
        with http_client(ctx) as client:
            while True:
                r = client.get(status_update_url)
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
    campaign: arguments.CampaignName.Required,
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

    with http_client(ctx) as client:
        r = client.patch(
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
        with http_client(ctx) as client:
            while True:
                r = client.get(status_update_url)
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
def advance_campaign(ctx: TypedContext, campaign: arguments.CampaignName.Required) -> None:
    """advances a paused campaign"""

    status_update_url = None

    with http_client(ctx) as client:
        r = client.post(
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
    #     with http_client(ctx) as client:
    #         while True:
    #             r = client.get(status_update_url)
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
    campaign: arguments.CampaignName.Required,
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


@app.command(name="audit")
def audit_campaign(
    ctx: TypedContext,
    campaign: arguments.CampaignName.Required,
    *,
    limit: options.limit = 10,
    actor: Annotated[str | None, typer.Option(help="Only show entries for this actor")] = None,
    since: Annotated[
        str | None,
        typer.Option(help="Only show entries at or after this ISO8601 datetime"),
    ] = None,
) -> None:
    """Show audit log entries for a campaign, newest first."""
    output_format = formatters.Formatters[ctx.obj.output_format]
    params: dict[str, str | int] = {
        "context.namespace": str(ctx.obj.campaign_id),
        "limit": limit,
        "sort": "-created_at",
    }
    if actor is not None:
        params["actor"] = actor
    if since is not None:
        params["since"] = since

    with http_client(ctx) as client:
        try:
            # An unknown campaign would produce an empty audit log, so check
            # that the campaign exists before querying the audit log.
            r = client.head(f"/campaigns/{ctx.obj.campaign_id}")
            if r.status_code == codes.NOT_FOUND:
                console.print(f"No such campaign: {ctx.obj.campaign_name}", style="red")
                raise typer.Exit(1)
            r.raise_for_status()

            r = client.get("/audit/", params=params)
            r.raise_for_status()
        except HTTPError as e:
            print(e)
            raise typer.Exit(1)

    match output_format:
        case formatters.Formatters.table if not r.json():
            console.print(f"No audit log entries for campaign {ctx.obj.campaign_name}")
        case formatters.Formatters.table:
            t = as_audit_table(
                r.json(), title=f"Audit Log: {ctx.obj.campaign_name}", caption=str(ctx.obj.campaign_id)
            )
            console.print(t)
        case formatters.Formatters.json:
            pretty = JSONHighlighter()
            Console().print(pretty(r.text))
        case formatters.Formatters.yaml:
            print(r.text)


@app.command(name="delete")
def delete_campaign(
    ctx: TypedContext,
    campaign: arguments.CampaignName.Required,
) -> None:
    """Deletes a campaign by ID"""
    with http_client(ctx) as client:
        r = client.delete(
            f"/campaigns/{ctx.obj.campaign_id}",
        )
        r.raise_for_status()
