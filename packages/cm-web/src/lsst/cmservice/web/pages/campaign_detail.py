# ruff: noqa
from functools import partial
from typing import TYPE_CHECKING, Any, Self, TypedDict

import networkx as nx
from httpx import AsyncClient
from nicegui import app, run, ui

from .. import api
from ..api.campaigns import toggle_campaign_state
from ..components import dicebear, storage, strings
from ..components.graph import nx_to_mermaid
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.configedit import configuration_edit
from ..lib.enum import MANIFEST_KIND_ICONS, StatusDecorators
from ..lib.timestamp import timestamp
from .common import CMPage


# TODO replace with a pydantic model
class CampaignDetailPageModel(TypedDict):
    campaign: dict[str, Any]
    nodes: list[dict[str, Any]]
    manifests: dict[str, Any]
    graph: nx.DiGraph | None
    logs: list[dict[str, Any]]


class CampaignDetailPage(CMPage):
    def create_node_card(self, node: dict) -> None:
        """Builds a card ui element with Node details, as used for nodes active
        in a campaign's graph.
        """
        if TYPE_CHECKING:
            assert self.model["graph"] is not None

        # Node is readonly if it is not the latest version of a node
        readonly = False

        node_graph_name = f"""{node["name"]}.{node["version"]}"""
        # Do not include the node card if the node is not in the graph
        if node_graph_name not in self.model["graph"].nodes:
            return None

        # a list of alternate versions for the same node
        node_versions = list(
            filter(
                lambda n: n["name"] == node["name"] and n["version"] != node["version"],
                self.model["nodes"],
            )
        )
        node_status = StatusDecorators[node["status"]]
        with ui.card().tight():
            with ui.row():
                # with ui.card_section().classes("grid grid-cols-[8rem_1fr] grid-rows-2 gap-2 min-w-0"):
                with ui.column().classes("items-center gap-2"):
                    # Large hero avatar link
                    with ui.link(target=f"/node/{node['id']}"):
                        ui.tooltip(node["id"])
                        with ui.avatar(square=True, color=None).classes("w-16 h-16"):
                            dicebear.identicon_icon(node["id"], color=node_status.hex)
                    ui.chip(
                        node["status"],
                        icon=node_status.emoji,
                        color=node_status.hex,
                    ).tooltip(node["status"])

                with ui.column().classes("gap-2 flex-grow min-w-0"):
                    with ui.row().classes("items-center"):
                        with ui.link(target=f"/node/{node['id']}").classes("text-black !no-underline"):
                            ui.label(node["name"]).tooltip(node["name"]).classes("font-black text-lg")

                        ui.chip(
                            node["kind"],
                            icon="fingerprint",
                            color="white",
                        ).tooltip("Node Kind")

                        node_version_chip = ui.chip(
                            node["version"],
                            icon="commit",
                            color="white",
                        ).tooltip("Node Version")

                    # ui.chip(
                    #     str(self.model["graph"].in_degree(node_graph_name)),  # pyright: ignore[reportArgumentType]
                    #     icon="input",
                    #     color="white",
                    # ).tooltip("Incoming Nodes")
                    # ui.chip(
                    #     str(self.model["graph"].out_degree(node_graph_name)),  # pyright: ignore[reportArgumentType]
                    #     icon="output",
                    #     color="white",
                    # ).tooltip("Downstream Nodes")

                    with ui.badge("!").classes("text-white bg-info") as newer_node_badge:
                        ui.tooltip("New Version Available").props("anchor='top middle' self='bottom middle'")
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
                    readonly = newer_node_badge.visible

            with ui.card_actions().props("align=right"):
                if node_created_at := node["metadata"].get("crtime"):
                    ui.chip(
                        timestamp(node_created_at, "%-d-%b %H:%M:%S UTC"),
                        icon="construction",
                        color="transparent",
                    ).tooltip("Created at").classes("text-sm")
                if node_updated_at := node["metadata"].get("mtime"):
                    ui.chip(
                        timestamp(node_updated_at, "%-d-%b %H:%M:%S UTC"),
                        icon="design_services",
                        color="transparent",
                    ).tooltip("Updated at").classes("text-sm")

                # FIXME after editing, the page model's version of the node is
                # not updated so will be out of sync, but these models are only
                # used for initial page `setup()` so it may not matter. We may
                # build a callback method for the configuration_edit() in order
                # to sync the page model with the new version.
                ui.button(
                    icon="preview",
                    color="dark",
                    on_click=partial(
                        configuration_edit,
                        manifest_id=node["id"],
                        namespace=node["namespace"],
                        readonly=readonly,
                        # callback=partial(sync_page_model, node["id"]),
                    ),
                ).props("style: flat").tooltip("View/Edit Node Configuration").bind_icon_from(
                    newer_node_badge, "visible", backward=lambda v: "preview" if v else "edit"
                )

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

    async def setup(self, client_: AsyncClient | None = None, *, campaign_id: str = "") -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        if client_ is None:
            raise RuntimeError("Campaign Detail page setup requires an httpx client")

        self.show_spinner()
        storage.initialize_client_storage()
        # the describe_one_campaign api helper builds a rich model of campaign
        # components, but it does not include library manifests.
        data = await api.describe_one_campaign(client=client_, id=campaign_id)

        self.campaign_id = campaign_id
        if campaign_id not in app.storage.client["state"].campaigns:
            app.storage.client["state"].campaigns[campaign_id] = {}

        self.model: CampaignDetailPageModel = {
            "campaign": data["campaign"],
            "nodes": data["nodes"],
            "manifests": {m["id"]: m for m in data["manifests"]},
            "graph": None,
            "logs": data["logs"],
        }
        self.model["graph"] = await run.cpu_bound(
            nx.node_link_graph,
            data["graph"],
            edges="edges",  # pyright: ignore[reportCallIssue]
        )
        app.storage.client["state"].campaigns[campaign_id]["status"] = self.model["campaign"]["status"]

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

        # with ui.expansion(
        #     "Library Manifests", caption=strings.LIBRARY_MANIFEST_TOOLIP, icon="extension"
        # ).classes("w-full"):
        #     ui.label("Library Manifests")
        #     # a row of 5 skeleton cards
        #     # this row should be scrollable <-> but not grow in height
        #     with ui.row().classes("w-full"):
        #         ...
        # ui.separator()

        with ui.expansion(
            "Campaign Manifests", caption=strings.CAMPAIGN_MANIFEST_TOOLTIP, icon="extension"
        ).classes("w-full"):
            await self.manifest_row()

        ui.separator()
        # Campaign Nodes
        with ui.row().classes("flex flex-wrap justify-center gap-2") as self.nodes_row:
            for node in sorted(
                self.model["nodes"], key=lambda x: x["metadata"].get("mtime", 0), reverse=True
            ):
                self.create_node_card(node)

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
        if TYPE_CHECKING:
            assert self.model["graph"] is not None

        with ui.expansion("Campaign Graph", icon="shape_line").classes("w-full") as self.graph_viz:
            ui.mermaid(nx_to_mermaid(self.model["graph"]), config={"securityLevel": "loose"}).classes(
                "w-full"
            )
            ui.on("node_click", lambda n: ui.navigate.to(f"/node/{n.args}"))

    @ui.refreshable_method
    def create_gauges(self) -> None:
        # Dashboard gauges
        with ui.row(align_items="center") as self.gauges_row:
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
                    log_count = len(self.model["logs"])
                    error_count = len([l for l in self.model["logs"] if l["detail"].get("error", None)])
                    ui.circular_progress(value=error_count, max=log_count, color="negative", size="xl")

    def campaign_status_decorator(self) -> None:
        """An icon representing the campaign state."""
        ui.icon("", size="xl", color="primary").bind_name_from(
            app.storage.client["state"].campaigns[self.campaign_id],
            "status",
            backward=lambda s: StatusDecorators[s].emoji,
            strict=False,
        )

    @ui.refreshable_method
    async def manifest_row(self, *, library: bool = False) -> None:
        """Produces a row of cards for Manifests. Each card displays the name,
        kind, and version of the manifest and has either a preview or an edit
        button. Library manifests are read-only.
        """
        with ui.row():
            for manifest in self.model["manifests"].values():
                readonly = manifest["version"] == 0
                if library and not readonly:
                    continue
                with ui.card():
                    with ui.column():
                        ui.chip(text=manifest["kind"].upper(), color="accent").classes("text-xs").props(
                            "outline square"
                        ).bind_icon_from(MANIFEST_KIND_ICONS, manifest["kind"])
                        ui.label(manifest["name"]).classes("text-subtitle2").tooltip(manifest["id"])
                    with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                        ui.chip(
                            manifest["version"],
                            icon="commit",
                            color="white",
                        ).tooltip("Manifest Version")
                        ui.button(
                            icon="preview" if readonly else "edit",
                            color="dark",
                            on_click=partial(
                                configuration_edit,
                                manifest_id=manifest["id"],
                                namespace=manifest["namespace"],
                                kind=manifest["kind"],
                                readonly=readonly,
                                callback=self.refresh_manifest_row,
                            ),
                        ).props("style: flat").tooltip("Edit Manifest Configuration")

    async def refresh_manifest_row(self, *args: Any, **kwargs: Any) -> None:
        """Wraps the refreshable manifest row with an IO call to update the
        page model first.
        """
        # TODO provide an api wrapper that specifically targets the manifests
        async with CLIENT_FACTORY.aclient() as client_:
            data = await api.describe_one_campaign(client=client_, id=self.campaign_id)
        self.model["manifests"] = {m["id"]: m for m in data["manifests"]}
        self.manifest_row.refresh()
