from functools import partial
from typing import Annotated

import httpx
import networkx as nx
from fastapi import Depends
from nicegui import run, ui

from .. import api
from ..api.campaigns import toggle_campaign_state
from ..components import dicebear
from ..components.graph import nx_to_mermaid
from ..lib.client import get_client
from ..lib.configdiff import patch_resource
from ..lib.enum import StatusDecorators
from ..lib.timestamp import timestamp
from .common import cm_frame


async def get_data(editor: ui.json_editor, dialog: ui.dialog) -> None:
    """Gets current data from a specified editor and submits it as a return
    value through the specified dialog.
    """
    data = await editor.run_editor_method("get")
    dialog.submit(data)


async def configuration_edit(manifest_id: str, namespace: str) -> None:
    """Display a Dialog with a JSON Editor component, loaded with the current
    configuration of the specified Manifest object. Data from the editor is
    returned when a "Done" button is pressed, otherwise any changes are
    discarded and the Dialog is dismissed with a None.

    If data is returned from the dialog, it is used to patch the Manifest
    resource.
    """
    # get current configuration of manifest/node from db
    manifest_response = await run.io_bound(api.get_one_node, id=manifest_id, namespace=namespace)
    manifest_url = manifest_response.headers["Self"]
    manifest = manifest_response.json()

    current_configuration = manifest.get("configuration", {})
    with ui.dialog().props("full-height") as dialog, ui.card().style("width: 75vw"):
        ui.label("Editing Node Configuration")
        editor = ui.json_editor(
            {"content": {"json": current_configuration}},
        ).classes("w-full h-full")
        with ui.card_actions():
            get_data_partial = partial(get_data, dialog=dialog, editor=editor)
            ui.button("Done", color="positive", on_click=get_data_partial).props("style: flat")
            ui.button("Cancel", color="negative", on_click=lambda: dialog.submit(None)).props("style: flat")

    result = await dialog
    if result is not None:
        # TODO run.io_bound
        await patch_resource(manifest_url, current_configuration, result)


@ui.page("/campaign/{campaign_id}")
async def campaign_detail(campaign_id: str, client_: Annotated[httpx.Client, Depends(get_client)]) -> None:
    """Builds a campaign detail page"""
    data = await run.io_bound(api.describe_one_campaign, client=client_, id=campaign_id)
    graph: nx.DiGraph = await run.cpu_bound(
        nx.node_link_graph,
        data["graph"],
        edges="edges",  # pyright: ignore[reportCallIssue]
    )

    campaign = data["campaign"]
    nodes = data["nodes"]  # all campaign nodes
    campaign_status = StatusDecorators[campaign["status"]]

    with cm_frame(campaign["name"], footers=[campaign["id"]]):
        # Mermaid graph diagram
        with ui.expansion("Campaign Graph", icon="shape_line").classes("w-full"):
            ui.mermaid(nx_to_mermaid(graph), config={"securityLevel": "loose"}).classes("w-full")
            ui.on("node_click", lambda n: ui.navigate.to(f"/node/{n.args}"))

        ui.separator()

        # Current campaign manifests
        with ui.expansion("Campaign Manifests", icon="extension").classes("w-full"):
            api.compile_campaign_manifests(id=campaign["id"], manifests=data["manifests"])

        ui.separator()

        # Dashboard gauges
        with ui.row(align_items="center"):
            element_size = "xl"
            with ui.card().classes("items-center"):
                ui.icon(campaign_status.emoji, size=element_size, color="primary")
                with ui.row():
                    campaign_running = campaign["status"] == "running"
                    campaign_toggle = partial(toggle_campaign_state, campaign=campaign)
                    ui.switch(on_change=campaign_toggle, value=campaign_running)
            with ui.card():
                ui.label("Nodes")
                with ui.row():
                    ui.circular_progress(
                        value=sum([n["status"] == "accepted" for n in nodes]),
                        max=len(nodes),
                        color="positive",
                        size=element_size,
                    )

            with ui.card():
                ui.label("Errors")
                with ui.row():
                    ui.circular_progress(value=0, max=100, color="negative", size=element_size)

        ui.separator()

        # Campaign Nodes
        with ui.row(align_items="stretch").classes("w-full flex-center"):
            for node in sorted(nodes, key=lambda x: x["metadata"].get("mtime", 0), reverse=True):
                node_graph_name = f"""{node["name"]}.{node["version"]}"""
                node_versions = list(
                    filter(
                        lambda n: n["name"] == node["name"] and n["version"] != node["version"],
                        nodes,
                    )
                )
                if (
                    node_graph_name in graph.nodes
                    and node["version"] == graph.nodes[node_graph_name]["version"]
                ):
                    campaign_detail_node_card(node, node_versions, graph)


def campaign_detail_node_card(node: dict, node_versions: list, graph: nx.DiGraph) -> None:
    """Builds a card ui element with Node details, as used for nodes active in
    a campaign's graph.
    """
    node_graph_name = f"""{node["name"]}.{node["version"]}"""
    node_status = StatusDecorators[node["status"]]
    with ui.card():
        with ui.row():
            with ui.card_section():
                with ui.link(target=f"/node/{node['id']}"):
                    with ui.avatar(square=True, color=None):
                        ui.tooltip(node["id"])
                        dicebear.identicon_icon(node["id"], color=node_status.hex)
            with ui.card_section():
                with ui.row().classes("items-center"):
                    ui.label(node["name"]).classes("bold text-lg font-black").tooltip(node["name"])
                    ui.chip(
                        node["status"],
                        icon=node_status.emoji,
                        color=node_status.hex,
                    ).tooltip(node["status"])
                with ui.row().classes("items-center"):
                    node_version_chip = ui.chip(
                        node["version"],
                        icon="commit",
                        color="white",
                    ).tooltip("Node Version")
                    ui.chip(
                        graph.in_degree(node_graph_name),
                        icon="input",
                        color="white",
                    ).tooltip("Incoming Nodes")
                    ui.chip(
                        graph.out_degree(node_graph_name),
                        icon="output",
                        color="white",
                    ).tooltip("Downstream Nodes")

                    newer_node_badge = (
                        ui.badge("!").classes("text-white bg-info").tooltip("New Version Available")
                    )
                    newer_node_badge.set_visibility(
                        len(
                            list(
                                filter(
                                    lambda n: n["version"] > node["version"],
                                    node_versions,
                                )
                            )
                        )
                        > 0
                    )
                    newer_node_badge.move(node_version_chip)

        with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
            if node_created_at := node["metadata"].get("crtime"):
                ui.chip(
                    timestamp(node_created_at, "%-d-%b %H:%M:%S UTC"),
                    icon="construction",
                    color="transparent",
                ).tooltip("Created at")
            if node_updated_at := node["metadata"].get("mtime"):
                ui.chip(
                    timestamp(node_updated_at, "%-d-%b %H:%M:%S UTC"),
                    icon="design_services",
                    color="transparent",
                ).tooltip("Updated at")

            ui.button(
                icon="edit",
                color="dark",
                on_click=partial(
                    configuration_edit,
                    manifest_id=node["id"],
                    namespace=node["namespace"],
                ),
            ).props("style: flat").tooltip("Edit Node Configuration")

        if len(node_versions):
            with ui.expansion("Other Versions").classes("w-full"):
                with ui.row():
                    for version in node_versions:
                        node_replacement_callback = partial(
                            api.nodes.replace_node,
                            n0=node["id"],
                            n1=version["id"],
                            namespace=node["namespace"],
                        )
                        ui.chip(
                            version["version"],
                            icon="commit",
                            color=StatusDecorators[version["status"]].hex,
                            on_click=node_replacement_callback,
                        ).tooltip(version["status"])
