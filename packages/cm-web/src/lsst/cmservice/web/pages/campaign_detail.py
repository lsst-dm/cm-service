from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, Self

import networkx as nx
from httpx import AsyncClient
from nicegui import app, run, ui
from nicegui.events import ClickEventArguments, GenericEventArguments, ValueChangeEventArguments

from .. import api
from ..components import dicebear, storage, strings
from ..components.dialog import AddStepEditorDialog, EditorContext, NewManifestEditorDialog, StepEditorDialog
from ..components.graph import nx_to_mermaid
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.configdiff import patch_resource
from ..lib.enum import MANIFEST_KIND_ICONS, StatusDecorators
from ..lib.models import STEP_MANIFEST_TEMPLATE
from ..lib.timestamp import timestamp
from .common import CMPage, CMPageModel


# TODO replace with a pydantic model
class CampaignDetailPageModel(CMPageModel):
    campaign: dict[str, Any]
    nodes: list[dict[str, Any]]
    manifests: dict[str, Any]
    graph: nx.DiGraph | None
    logs: list[dict[str, Any]]


class CampaignDetailPage(CMPage[CampaignDetailPageModel]):
    """A campaign detail page with a graph visualization, status gauges, and
    access to manifest and node makeup of the campaign.

    The drawer menu provides access to tools and filters.
    """

    constrain_graph_viz: bool = True
    nodes_view: Literal["cards", "table"] = "cards"
    node_content: ui.element

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
        with ui.card().classes("pt-0 pb-0 pl-0 pr-2"):
            with ui.row():
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

                with ui.column().classes("gap-0 flex-grow min-w-0 items-left"):
                    # with ui.row().classes("items-center"):
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

            with ui.card_actions().classes("w-full"):
                show_node_created_at = False
                if show_node_created_at and (node_created_at := node["metadata"].get("crtime")):
                    ui.chip(
                        timestamp(node_created_at, "%-d-%b %H:%M:%S UTC"),
                        icon="construction",
                        color="transparent",
                    ).tooltip("Created at").classes("text-xs")
                if node_updated_at := node["metadata"].get("mtime"):
                    ui.chip(
                        timestamp(node_updated_at, "%-d-%b %H:%M:%S UTC"),
                        icon="design_services",
                        color="transparent",
                    ).tooltip("Updated at").classes("text-xs")

                # FIXME after editing, the page model's version of the node is
                # not updated so will be out of sync, but these models are only
                # used for initial page `setup()` so it may not matter. We may
                # build a callback method for the configuration_edit() in order
                # to sync the page model with the new version.
                ui.space()
                node_edit_button = (
                    ui.button(
                        icon="preview",
                        color="dark",
                        on_click=self.handle_node_edit,
                    )
                    .classes("")
                    .props(f"flat round size=sm id={node['id']}")
                    .tooltip("View/Edit Node Configuration")
                    .bind_icon_from(
                        newer_node_badge, "visible", backward=lambda v: "preview" if v else "edit"
                    )
                )
                if (node["kind"] in ["breakpoint", "start", "end"]) or readonly:
                    node_edit_button.disable()
                    node_edit_button.icon = "edit_off"
                    node_edit_button.props(add="readonly")

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

    def drawer_contents(self) -> None:
        ui.button(
            "New Step",
            icon="add",
            color="accent",
            on_click=lambda e: AddStepEditorDialog.click(
                e,
                EditorContext(
                    namespace=self.campaign_id,
                    page=self,
                    name_validators=["validate_step_name"],
                    callback=self.apply_new_step,
                ),
                title="Add New Step",
            ),
        ).classes("w-full")

        with ui.row().classes("w-full flex items-center"):
            ui.label("Nodes As:").classes("text-sm flex-1")
            ui.toggle(
                {"cards": "Cards", "table": "Table"}, value="cards", on_change=self.handle_node_display_toggle
            ).classes("flex-1").bind_value(self, "nodes_view", strict=False)

    async def footer_contents(self) -> None:
        ui.label().classes("text-xs").bind_text_from(self, "campaign_id", strict=False)

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

        # events emitted by the graph viz component
        ui.on("node_click", lambda n: ui.navigate.to(f"/node/{n.args}"))

        return self

    @ui.refreshable_method
    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """
        if TYPE_CHECKING:
            assert self.model["graph"] is not None

        with ui.expansion("Campaign Graph", icon="shape_line").classes("w-full") as self.graph_viz:
            self.create_graph_viz()

        ui.separator()
        self.create_gauges()
        ui.separator()

        with ui.expansion(
            "Campaign Manifests", caption=strings.CAMPAIGN_MANIFEST_TOOLTIP, icon="extension"
        ).classes("w-full"):
            await self.manifest_row()

        ui.separator()
        # Campaign Nodes
        self.node_content = ui.element("div").classes("w-full h-full pt-[0.5rem] pb-[0.5rem] overflow-y-auto")
        await self.create_node_table()
        await self.create_node_cards()

        # Campaign FAB
        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            with ui.fab("save_as", direction="up"):
                clone_navigator = partial(ui.navigate.to, f"/clone/{self.campaign_id}")
                export_navigator = partial(ui.notify, f"Export Campaign {self.campaign_id}...")
                ui.fab_action("ios_share", label="export", on_click=export_navigator).disable()
                ui.fab_action("copy_all", label="clone", on_click=clone_navigator)

        self.hide_spinner()

    @ui.refreshable_method
    async def create_node_cards(self) -> None:
        """Creates a card for each Campaign Node. The cards are added to a
        flex row with wrapping, and y-scrolling is enabled on an outer div.
        """
        if self.nodes_view != "cards":
            return None

        with self.node_content:
            with ui.row().classes("h-full flex flex-wrap justify-center gap-2") as self.nodes_row:
                for node in sorted(
                    self.model["nodes"], key=lambda x: x["metadata"].get("mtime", 0), reverse=True
                ):
                    self.create_node_card(node)

    async def get_node_edit_button(self) -> None:
        """Creates an edit or preview button suitable for a table cell"""
        ui.button(
            icon="edit",
            color="dark",
        ).props("flat round size=sm").tooltip("View/Edit Node Configuration").on(
            "click",
            js_handler="() => emit(props.row.id)",
            handler=self.handle_node_edit,
        )

    @ui.refreshable_method
    async def create_node_table(self) -> None:
        """Creates a table element listing Campaign Nodes."""
        if self.nodes_view != "table":
            return None

        node_columns: list[dict[str, Any]] = [
            {"name": "id", "label": "ID", "field": "id", "classes": "hidden", "headerClasses": "hidden"},
            {"name": "name", "label": "Name", "field": "name", "sortable": True},
            {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "center"},
            {
                "name": "icon",
                "label": "Icon",
                "field": "icon",
                "classes": "hidden",
                "headerClasses": "hidden",
            },
            {"name": "kind", "label": "Kind", "field": "kind", "sortable": True},
            {
                "name": "max_version",
                "label": "Newest Version",
                "field": "max_version",
                "classes": "hidden",
                "headerClasses": "hidden",
            },
            {"name": "updated", "label": "Updated At", "field": "updated", "sortable": True},
            {"name": "version", "label": "Version", "field": "version", "sortable": True},
            {"name": "edit", "label": "View/Edit", "field": "edit"},
            {
                "name": "readonly",
                "label": "Readonly",
                "field": "readonly",
                "classes": "hidden",
                "headerClasses": "hidden",
            },
        ]
        node_rows: list[dict[str, Any]] = [
            {
                "id": node["id"],
                "name": node["name"],
                "status": node["status"],
                "icon": StatusDecorators[node["status"]].emoji,
                "kind": node["kind"],
                "version": node["version"],
                "max_version": node["version"],
                "updated": timestamp(node["metadata"].get("mtime", 0), "%-d-%b %H:%M:%S UTC"),
                "edit": None,
                "readonly": False,
            }
            for node in sorted(self.model["nodes"], key=lambda x: x["metadata"].get("mtime", 0), reverse=True)
        ]

        with self.node_content:
            node_table = ui.table(columns=node_columns, rows=node_rows).classes("w-full h-full overflow-auto")

        with node_table.add_slot("body-cell-edit"):
            with node_table.cell("edit"):
                await self.get_node_edit_button()
        with node_table.add_slot("body-cell-status"):
            with node_table.cell("status"):
                ui.chip().props(":label=props.row.status :color=props.row.status :icon=props.row.icon")
        with node_table.add_slot("body-cell-version"):
            with node_table.cell("version"):
                ui.badge().props("""
                    :label="props.value"
                    :color="parseInt(props.row.max_version) > parseInt(props.value) ? 'warning' : 'primary'"
                """)

    @ui.refreshable_method
    def create_graph_viz(self) -> None:
        async def toggle_graph_constraint() -> None:
            """Callable to change the mermaid graph viz from constrained (fits
            the page) to unconstrained (larger/zoom with scrollbars).
            """
            self.constrain_graph_viz = not self.constrain_graph_viz
            self.create_graph_viz.refresh()

        if TYPE_CHECKING:
            assert self.model["graph"] is not None

        with ui.element("div").classes("w-full max-h-[16rem] overflow-auto relative"):
            ui.mermaid(
                nx_to_mermaid(self.model["graph"], constrain=self.constrain_graph_viz),
                config={"securityLevel": "loose"},
            ).classes("min-w-full")

        ui.button(
            icon="fullscreen" if self.constrain_graph_viz else "fit_screen",
            on_click=toggle_graph_constraint,
        ).props("fab-mini color=accent").classes(
            "absolute top-2 left-2 z-10 opacity-50 hover:opacity-100"
        ).tooltip("Zoom graph view")

    @ui.refreshable_method
    def create_gauges(self) -> None:
        # Dashboard gauges
        gauge_card_classes = "w-22 h-30 pt-[0.5rem] pb-[0.5rem] items-center"
        with ui.row().classes("w-full ml-4 mr-4 items-center") as self.gauges_row:
            with ui.card().classes(gauge_card_classes):
                self.campaign_status_decorator()
                with ui.row():
                    campaign_running = self.model["campaign"]["status"] == "running"
                    campaign_terminal: bool = self.model["campaign"]["status"] in (
                        "accepted",
                        "failed",
                        "rejected",
                    )
                    campaign_toggle = partial(api.toggle_campaign_state, campaign=self.model["campaign"])
                    campaign_switch = ui.switch(on_change=campaign_toggle, value=campaign_running)
                    campaign_switch.enabled = not campaign_terminal
            with ui.card().classes(gauge_card_classes):
                ui.label("Nodes")
                with ui.row():
                    ui.circular_progress(
                        value=sum([n["status"] == "accepted" for n in self.model["nodes"]]),
                        max=len(self.model["nodes"]),
                        color="positive",
                        size="xl",
                    )

            with ui.card().classes(gauge_card_classes):
                ui.label("Errors")
                with ui.row():
                    log_count = len(self.model["logs"])
                    error_count = len([log for log in self.model["logs"] if log["detail"].get("error", None)])
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
                        edit_button = (
                            ui.button(
                                icon="preview" if readonly else "edit",
                                color="dark",
                                on_click=self.handle_manifest_edit,
                            )
                            .props(f"flat round size=sm id={manifest['id']}")
                            .tooltip("Edit Manifest Configuration")
                        )

                        if readonly:
                            edit_button.props(add="readonly")

    async def refresh_manifest_row(self, *args: Any, **kwargs: Any) -> None:
        """Wraps the refreshable manifest row with an IO call to update the
        page model first.
        """
        # TODO provide an api wrapper that specifically targets the manifests
        async with CLIENT_FACTORY.aclient() as client_:
            data = await api.describe_one_campaign(client=client_, id=self.campaign_id)
        self.model["manifests"] = {m["id"]: m for m in data["manifests"]}
        self.manifest_row.refresh()

    async def validate_step_name(self, data: str | None, ctx: EditorContext) -> str | None:
        """Method to validate the name of a new step, used as a validation
        callback for the new step editor dialog.
        """
        if data in [n["name"] for n in self.model["nodes"]]:
            return "Name must be unique in the Campaign"
        return None

    async def apply_new_step(self, manifest: dict) -> dict:
        """Callback for applying a new step for a campaign via the new step
        dialog.
        """
        self.show_spinner()
        # This method trusts that the editor delivers a valid manifest for a
        # new step in the current campaign.
        ancestor_id = manifest["metadata"].pop("ancestor", None)

        # clean up the manifest in a step-specific way
        _ = manifest.get("metadata", {}).pop("uuid", None)

        if ancestor_id is None:
            ui.notify("No valid ancestor selected for step", type="negative")
            return manifest

        try:
            # 1. create the Node object in the campaign
            if not await api.put_manifest_list([manifest]):
                raise RuntimeError("An error occurred creating the new step")

            # 1.5 get the node we just created
            r = await api.get_one_node(
                manifest["metadata"]["name"], namespace=manifest["metadata"]["namespace"]
            )
            if r is not None:
                r.raise_for_status()
                new_step = r.json()
            else:
                raise RuntimeError("An error occurred fetching the new step")

            # 2. call the insert operation with the new node
            if not await api.insert_or_append_node(
                n0=ancestor_id,
                n1=new_step["id"],
                namespace=manifest["metadata"]["namespace"],
                operation="insert",
            ):
                raise RuntimeError("An error occurred adding the new step to the graph")

        except Exception as e:
            ui.notify(e, type="negative")
        finally:
            self.hide_spinner()
            return manifest

    async def handle_node_edit(self, data: ClickEventArguments | GenericEventArguments) -> None:
        """Callback for edit button on Node cards"""
        # Data input should include the node id, and we could defer dialog
        # behaviors to this callback to simplify the logic in the Node card
        match data:
            case GenericEventArguments():
                target_node = data.args
            case ClickEventArguments():
                target_node = data.sender.props.get("id", None)
            case _:
                target_node = None  # type: ignore[unreachable]
        if (
            target_node is None
            or (node_response := await api.get_one_node(target_node, self.campaign_id)) is None
        ):
            return None
        node_url = node_response.headers["Self"]
        node = node_response.json()
        node_name = node["name"]
        readonly_editor = any(
            [
                (node.get("status", "") != "waiting"),
                ("readonly" in data.sender.props),
                (data.sender.props["icon"] == "preview"),
            ]
        )

        node_manifest = deepcopy(STEP_MANIFEST_TEMPLATE) | {
            "metadata": {
                "kind": node["kind"],
                "name": node["name"],
                "namespace": node["namespace"],
                "status": node["status"],
            },
            "spec": deepcopy(node["configuration"]),
        }
        ctx = EditorContext(
            page=self,
            namespace=str(self.campaign_id),
            name=node_name,
            kind=node["kind"],
            allow_name_change=False,
            allow_kind_change=False,
            readonly=readonly_editor,
        )
        dialog = StepEditorDialog(
            ctx,
            title=f"Editing Step {node_name}",
            initial_model=node_manifest,
        )
        result: dict[str, Any] = await dialog
        dialog.clear()

        if result is None or ctx.readonly:
            return None

        await patch_resource(node_url, node["configuration"], result["spec"])

    async def handle_manifest_edit(self, data: ClickEventArguments) -> None:
        """Callback for edit button on Manifest cards"""
        target_node = data.sender._props.get("id", None)
        if (
            target_node is None
            or (node_response := await api.get_one_manifest(namespace=self.campaign_id, id=target_node))
            is None
        ):
            ui.notify("Could not load manifest to edit", type="negative")
            return None
        node_url = node_response.headers["Self"]
        node = node_response.json()
        node_name = node["name"]
        readonly_editor = any(
            [
                ("readonly" in data.sender.props),
                (data.sender.props["icon"] == "preview"),
            ]
        )

        node_manifest = deepcopy(STEP_MANIFEST_TEMPLATE) | {
            "kind": node["kind"],
            "metadata": {"name": node["name"], "namespace": node["namespace"]},
            "spec": deepcopy(node["spec"]),
        }
        ctx = EditorContext(
            page=self,
            namespace=str(self.campaign_id),
            name=node_name,
            kind=node["kind"],
            allow_name_change=False,
            allow_kind_change=False,
            readonly=readonly_editor,
        )
        dialog = NewManifestEditorDialog(
            ctx,
            title=f"Editing Manifest {node_name}",
            initial_model=node_manifest,
        )
        result: dict[str, Any] = await dialog
        dialog.clear()

        if result is None or ctx.readonly:
            return None

        await patch_resource(node_url, node["spec"], result["spec"])
        await self.refresh_manifest_row()

    async def handle_node_display_toggle(self, data: ValueChangeEventArguments) -> None:
        """Toggle and refresh the Node display area based on the node display
        toggle control."""
        match data:
            case ValueChangeEventArguments(value="table"):
                self.node_content.clear()
                await self.create_node_table.refresh()
            case ValueChangeEventArguments(value="cards"):
                self.node_content.clear()
                await self.create_node_cards.refresh()
            case _:
                ...
