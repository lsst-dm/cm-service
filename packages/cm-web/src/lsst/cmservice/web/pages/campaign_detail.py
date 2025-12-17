# ruff: noqa
from functools import partial
from typing import TYPE_CHECKING, Annotated, Any, Self, TypedDict

import networkx as nx
from fastapi import Depends
from httpx import AsyncClient
from nicegui import app, run, ui

from .. import api
from ..api.campaigns import toggle_campaign_state
from ..components import dicebear, storage
from ..components.graph import nx_to_mermaid
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.configdiff import patch_resource
from ..lib.enum import StatusDecorators
from ..lib.timestamp import timestamp
from ..settings import settings
from .common import CMPage, cm_frame


# TODO replace with a pydantic model
class CampaignDetailPageModel(TypedDict):
    campaign: dict[str, Any]
    nodes: list[dict[str, Any]]
    manifests: dict[str, Any]
    graph: nx.DiGraph | None


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
    manifest_response = await api.get_one_node(id=manifest_id, namespace=namespace)
    manifest_url = manifest_response.headers["Self"]
    manifest = manifest_response.json()

    current_configuration = manifest.get("configuration", {})
    with ui.dialog().props("full-height") as dialog, ui.card().style("width: 75vw"):
        ui.label("Editing Node Configuration")
        editor = ui.json_editor(
            {"content": {"json": current_configuration}, "mode": "text"},
        ).classes("w-full h-full")
        with ui.card_actions():
            get_data_partial = partial(get_data, dialog=dialog, editor=editor)
            ui.button("Done", color="positive", on_click=get_data_partial).props("style: flat")
            ui.button("Cancel", color="negative", on_click=lambda: dialog.submit(None)).props("style: flat")

    result = await dialog
    if result is not None:
        # TODO run.io_bound
        await patch_resource(manifest_url, current_configuration, result)


@ui.page("/Xcampaign/{campaign_id}", response_timeout=settings.timeout)
async def campaign_detail(
    campaign_id: str, client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)]
) -> None:
    """Builds a campaign detail page"""
    storage.initialize_client_storage()
    campaign = {"name": "hello", "id": "world"}
    if campaign_id not in app.storage.client["state"].campaigns:
        app.storage.client["state"].campaigns[campaign_id] = {}
    app.storage.client["state"].campaigns[campaign_id]["status"] = campaign["status"]

    with cm_frame(campaign["name"], footers=[campaign["id"]]):
        ...
        # Library manifests
        # with ui.expansion("Library Manifests", icon="extension").classes("w-full"):
        #     await api.compile_campaign_manifests()

        # ui.separator()

        # Current campaign manifests
        # with ui.expansion("Campaign Manifests", icon="extension").classes("w-full"):
        #     await api.compile_campaign_manifests(campaign_id=campaign["id"], manifests=data["manifests"])

        # Campaign Nodes
        # with ui.row(align_items="stretch").classes("w-full flex-center"):
        #     for node in sorted(nodes, key=lambda x: x["metadata"].get("mtime", 0), reverse=True):
        #         node_graph_name = f"""{node["name"]}.{node["version"]}"""
        #         node_versions = list(
        #             filter(
        #                 lambda n: n["name"] == node["name"] and n["version"] != node["version"],
        #                 nodes,
        #             )
        #         )
        #         if (
        #             node_graph_name in graph.nodes
        #             and node["version"] == graph.nodes[node_graph_name]["version"]
        #         ):
        #             campaign_detail_node_card(node, node_versions, graph)


class CampaignDetailPage(CMPage):
    async def render(self) -> None:
        """Method to create main content for page.

        Subclasses should use the `create_content()` method, which is called
        from within the content column's context manager.
        """
        with self.content:
            await self.create_content()

    async def minimal_node_card(self, node: dict) -> None:
        with ui.card():
            ui.label(node["name"])
            with ui.row():
                with ui.card_section():
                    ui.label(node["status"])
                with ui.card_section():
                    ui.label(node["status"])

            with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                if node_created_at := node["metadata"].get("crtime"):
                    ui.chip(
                        timestamp(node_created_at, "%-d-%b %H:%M:%S UTC"),
                        # icon="edit",
                        color="transparent",
                    ).tooltip("Created at")
                if node_updated_at := node["metadata"].get("mtime"):
                    ui.chip(
                        timestamp(node_updated_at, "%-d-%b %H:%M:%S UTC"),
                        # icon="design_services",
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

    async def campaign_detail_node_card(self, node: dict) -> None:
        """Builds a card ui element with Node details, as used for nodes active
        in a campaign's graph.
        """
        if TYPE_CHECKING:
            assert self.model["graph"] is not None

        # a list of alternate versions for the same node
        node_versions = list(
            filter(
                lambda n: n["name"] == node["name"] and n["version"] != node["version"],
                self.model["nodes"],
            )
        )
        node_graph_name = f"""{node["name"]}.{node["version"]}"""
        node_status = StatusDecorators[node["status"]]
        with ui.card():
            with ui.row():
                # with ui.card_section():
                #     with ui.link(target=f"/node/{node['id']}"):
                #         ui.avatar(square=True, color="accent").tooltip(node["id"])
                # with ui.avatar(square=True, color=None):
                #     ui.tooltip(node["id"])
                #     dicebear.identicon_icon(node["id"], color=node_status.hex)

                with ui.card_section():
                    with ui.row().classes("items-center"):
                        ui.label(node["name"]).classes("bold text-lg font-black").tooltip(node["name"])
                        ui.chip(
                            node["status"],
                            # icon=node_status.emoji,
                            color=node_status.hex,
                        ).tooltip(node["status"])
                    with ui.row().classes("items-center"):
                        ui.chip(
                            node["kind"],
                            # icon="fingerprint",
                            color="white",
                        ).tooltip("Node Kind")
                        node_version_chip = ui.chip(
                            node["version"],
                            icon="commit",
                            color="white",
                        ).tooltip("Node Version")
                        ui.chip(
                            self.model["graph"].in_degree(node_graph_name),  # pyright: ignore[reportArgumentType]
                            # icon="input",
                            color="white",
                        ).tooltip("Incoming Nodes")
                        ui.chip(
                            self.model["graph"].out_degree(node_graph_name),  # pyright: ignore[reportArgumentType]
                            # icon="output",
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
                        # icon="construction",
                        color="transparent",
                    ).tooltip("Created at")
                if node_updated_at := node["metadata"].get("mtime"):
                    ui.chip(
                        timestamp(node_updated_at, "%-d-%b %H:%M:%S UTC"),
                        # icon="design_services",
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

    def drawer_contents(self) -> None: ...

    async def setup(self, client_: AsyncClient, campaign_id: str) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.show_spinner()
        storage.initialize_client_storage()
        self.campaign_id = campaign_id
        self.model: CampaignDetailPageModel = {
            "campaign": {},
            "nodes": [],
            "manifests": {},
            "graph": None,
        }
        data = await api.describe_one_campaign(client=client_, id=campaign_id)
        self.model["graph"] = await run.cpu_bound(
            nx.node_link_graph,
            data["graph"],
            edges="edges",  # pyright: ignore[reportCallIssue]
        )
        self.model["campaign"] = data["campaign"]
        self.model["nodes"] = data["nodes"]
        self.breadcrumbs.append(data["campaign"]["name"])
        self.create_header.refresh()

        return self

    @ui.refreshable_method
    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """
        if TYPE_CHECKING:
            assert self.model["graph"] is not None

        self.create_graph_viz()
        ui.separator()
        self.create_gauges()
        ui.separator()
        ui.label("Campaign and Library Manifests")
        # TODO manifests
        ui.separator()
        # Campaign Nodes
        with ui.row(align_items="stretch").classes("w-full flex-center") as self.nodes_row:
            for node in sorted(
                self.model["nodes"], key=lambda x: x["metadata"].get("mtime", 0), reverse=True
            ):
                node_graph_name = f"""{node["name"]}.{node["version"]}"""
                if (
                    node_graph_name in self.model["graph"].nodes
                    and node["version"] == self.model["graph"].nodes[node_graph_name]["version"]
                ):
                    await self.campaign_detail_node_card(node)

        # Campaign FAB
        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            with ui.fab("save_as", direction="up"):
                clone_navigator = partial(ui.navigate.to, f"/clone/{self.campaign_id}")
                export_navigator = partial(ui.notify, f"Export Campaign {self.campaign_id}...")
                ui.fab_action("ios_share", label="export", on_click=export_navigator).disable()
                ui.fab_action("copy_all", label="clone", on_click=clone_navigator)

        with self.footer:
            ui.label().classes("text-xs").bind_text_from(self, "campaign_id", strict=False)

        self.hide_spinner()

    @ui.refreshable_method
    def create_graph_viz(self) -> None:
        with ui.expansion("Campaign Graph", icon="shape_line").classes("w-full"):
            ui.mermaid(nx_to_mermaid(self.model["graph"]), config={"securityLevel": "loose"}).classes(
                "w-full"
            )
            ui.on("node_click", lambda n: ui.navigate.to(f"/node/{n.args}"))

    @ui.refreshable_method
    def create_gauges(self) -> None:
        # Dashboard gauges
        with ui.row(align_items="center"):
            with ui.card().classes("items-center"):
                self.campaign_status_decorator()
                with ui.row():
                    campaign_running = self.model["campaign"]["status"] == "running"
                    campaign_terminal: bool = self.model["campaign"]["status"] in (
                        "accepted",
                        "failed",
                        "rejected",
                    )
                    campaign_toggle = partial(toggle_campaign_state, campaign=self.model["campaign"])
                    campaign_switch = ui.switch(on_change=campaign_toggle, value=campaign_running)
                    campaign_switch.enabled = not campaign_terminal
            with ui.card():
                ui.label("Nodes")
                with ui.row():
                    ui.circular_progress(
                        value=sum([n["status"] == "accepted" for n in self.model["nodes"]]),
                        max=len(self.model["nodes"]),
                        color="positive",
                        size="xl",
                    )

            with ui.card():
                ui.label("Errors")
                with ui.row():
                    ui.circular_progress(value=0, max=100, color="negative", size="xl")

    @ui.refreshable_method
    def campaign_status_decorator(self) -> None:
        current_decorator = StatusDecorators[self.model["campaign"]["status"]]
        ui.icon(current_decorator.emoji, size="xl", color="primary")


@ui.page("/campaign/{campaign_id}", response_timeout=settings.timeout)
async def campaign_detail_page(
    campaign_id: str, client_: Annotated[AsyncClient, Depends(CLIENT_FACTORY.get_aclient)]
) -> None:
    """Builds a campaign detail page"""
    await ui.context.client.connected()
    if page := await CampaignDetailPage(title="Campaign Detail").setup(client_, campaign_id):
        await page.render()
