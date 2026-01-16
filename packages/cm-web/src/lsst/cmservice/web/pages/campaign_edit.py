"""Page and supporting functions for a Campaign's Edit Mode."""

import json
from functools import partial
from operator import itemgetter
from typing import Any, TypedDict
from uuid import UUID, uuid5

import networkx as nx
import yaml
from httpx import AsyncClient
from nicegui import run, ui
from nicegui.events import ClickEventArguments, GenericEventArguments, ValueChangeEventArguments

from lsst.cmservice.common.yaml import str_representer

from .. import api
from ..components.button import ToggleButton
from ..lib.canvas import nx_to_flow
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import MANIFEST_KIND_ICONS
from .common import CMPage

yaml.add_representer(str, str_representer)


STEP_SPEC_TEMPLATE: dict[str, Any] = {
    "bps": {
        "pipeline_yaml": "${DRP_PIPE_DIR}/path/to/pipeline.yaml#anchor",
    },
    "groups": None,
    "predicates": [],
}

STEP_MANIFEST_TEMPLATE: dict[str, Any] = {
    "apiVersion": "io.lsst.cmservice/v1",
    "kind": "node",
    "metadata": {},
    "spec": {},
}


# TODO replace with a pydantic model
class CampaignPageModel(TypedDict):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    spec: dict[str, dict[str, Any]]
    campaign: dict[str, Any]
    manifests: dict[str, Any]


class CampaignEditPage(CMPage):
    """The campaign edit view has a ribbon for accessing and editing
    Manifests and a canvas area for manipulating a graph. Each node in the
    graph will have an edit button.

    No objects are written to the database until the SAVE button in the
    menu drawer is used. Alternately, the EXPORT button will allow a down-
    load of the campaign in YAML format.
    """

    def edit_campaign_name(self) -> None:
        """A row of elements for editing high-level campaign details, such as
        the name.
        """
        with ui.row().classes("shrink-0 p-1 w-full"):
            ui.input(label="Campaign Name", on_change=self.handle_campaign_name_change).bind_value(
                self, "campaign_name"
            ).classes("w-48")

            # Campaign Manifests
            self.edit_campaign_manifests()

    def edit_campaign_manifests(self) -> None:
        """Renders an expansion group containg cards for editing campaign
        manifests.
        """
        with (
            ui.expansion(
                "Configuration Manifests", icon="extension", caption="Edit or add configuration manifests"
            ).classes("w-full"),
            ui.row().classes("w-full flex-nowrap gap-4 py-2 overflow-x-auto"),
        ):
            for manifest_id, manifest in self.model["manifests"].items():
                with ui.card().classes("m-1 p-1 shrink-1"):
                    with ui.card_section():
                        with ui.column():
                            ui.chip(text=manifest["kind"].upper(), color="accent").classes("text-xs").props(
                                "outline square"
                            ).bind_icon_from(MANIFEST_KIND_ICONS, manifest["kind"])
                            ui.input(label="Manifest Name").bind_value(
                                self.model["manifests"][manifest_id]["metadata"], "name"
                            ).classes("text-sm")
                    with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                        ui.space()
                        ToggleButton(color="dark").props("style: flat").tooltip(
                            "Set as default manifest for campaign"
                        )
                        ui.button(
                            icon="edit",
                            color="dark",
                            on_click=partial(self.manifest_edit, manifest_id),
                        ).props("style: flat").tooltip("Edit Manifest Configuration")

    def create_campaign_canvas(self) -> None:
        """A section containing a Canvas component for editing a campaign
        graph.
        """
        with (
            ui.element("div")
            .props("id=canvas-container")
            .classes("flex-1 min-h-0 w-full border-1 border-black")
        ):
            ui.run_javascript(f"""
                window.flowInstance = initializeFlow("canvas-container", {{
                    nodes: {self.initial_flow_nodes},
                    edges: {self.initial_flow_edges},
                    onClick: (data) => emitEvent("edit", data)
                }});
            """)
            ui.on("edit", self.handle_node_edit)

    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """
        # The canvas component requires a container with a specific height.
        # This div with a calculated height supplies that requirement.
        with (
            ui.element("div")
            .classes("flex flex-col p-0 m-0 w-full")
            .style("height: calc(100vh - 72px - 66px);")
        ):
            self.edit_campaign_name()
            self.create_step_editor()
            self.create_manifest_editor()
            self.create_campaign_canvas()

        # setup listeners
        ui.on("canvasExported", self.handle_exported_canvas)

        ui.run_javascript("""
            window.addEventListener("canvasExported", (e) => {
                emitEvent("canvasExported", e.detail);
            });
        """)

        with self.footer:
            ui.label().classes("text-xs").bind_text_from(self, "campaign_id", strict=False)

    def drawer_contents(self) -> None:
        """Right-side menu drawer contents rendered in a ui.column."""
        ui.button("Save", icon="save", on_click=self.handle_upload).classes("w-50")
        ui.button("Export", icon="save_alt", on_click=self.handle_export).classes("w-50")
        ui.button("Import", icon="file_upload").classes("w-50").disable()

    def create_step_editor(self) -> None:
        """Creates a Dialog for editing a step or node in the graph canvas."""
        with ui.dialog().classes("h-dvh w-full") as self.edit_dialog, ui.card().classes("w-full"):
            ui.label("Editing Step Configuration").classes("text-subtitle1")

            with ui.row().classes("w-full items-baseline"):
                with ui.dropdown_button("Grouping", auto_close=True) as self.group_option:
                    self.group_option.tooltip("Apply a grouping template spec to the Step")
                    ui.item("No Grouping", on_click=self.set_group_config).props("id=grouping_none")
                    ui.item("Fixed-Value Grouping", on_click=self.set_group_config).props("id=grouping_fixed")
                    ui.item("Query Grouping", on_click=self.set_group_config).props("id=grouping_query")

                ui.input_chips(
                    "Manifest Selectors",
                    # TODO
                    # . on_change=self.register_step_label_selectors,
                    # . validation=self.validate_manifest_label,
                ).tooltip("A collection of kind:name manifest selectors for the Step.")

            # Create an empty editor for reference and reuse
            self.editor = ui.json_editor(
                {
                    "content": {"json": {}},
                    "mode": "text",
                    "modes": ["text", "tree"],
                }
            ).classes("h-full w-full")

            with ui.card_actions():
                ui.button("Done", color="positive", on_click=self.save_node_edit).props("flat")
                ui.button("Cancel", color="negative", on_click=self.edit_dialog.close).props("flat")

    def create_manifest_editor(self) -> None:
        """Creates a Dialog for editing a manifest."""
        with ui.dialog().props("h-dvh w-full") as self.manifest_edit_dialog, ui.card().classes("w-full"):
            ui.label("Editing Manifest Configuration").classes("text-subtitle1")

            self.manifest_editor = ui.codemirror(
                value="# placeholder", language="YAML", highlight_whitespace=False
            ).classes("h-full w-full")
            with ui.card_actions():
                ui.button("Done", color="positive", on_click=self.save_manifest_edit).props("flat")
                ui.button("Cancel", color="negative", on_click=self.manifest_edit_dialog.close).props("flat")

    async def handle_node_edit(self, data: GenericEventArguments) -> None:
        """Callback target for "edit" events emitted by nodes on the canvas."""
        await self.configuration_edit(data.args)

    async def configuration_edit(self, step_id: str) -> None:
        """Display a Dialog with a JSON Editor component, loaded with the
        current configuration of the specified Manifest object. Data from the
        editor is returned when a "Done" button is pressed, otherwise any
        changes are discarded and the Dialog is dismissed with a None.
        """
        # If there is no configuration for this step in the page's model, use
        # the default template contents.
        current_configuration = self.model["spec"].get(step_id, STEP_SPEC_TEMPLATE)
        self.current_editor_node_id = step_id
        self.editor.run_editor_method("set", {"json": current_configuration})
        self.edit_dialog.open()

    async def manifest_edit(self, manifest_id: str) -> None:
        """Display a Dialog with a JSON Editor component, loaded with the
        current configuration of the specified Manifest object. Data from the
        editor is returned when a "Done" button is pressed, otherwise any
        changes are discarded and the Dialog is dismissed with a None.
        """
        current_configuration = self.model["manifests"].get(manifest_id, {}).get("spec", {})
        current_yaml = yaml.dump(current_configuration)
        self.current_editor_manifest_id = manifest_id
        self.manifest_edit_dialog.open()
        self.manifest_editor.set_value(current_yaml)
        self.manifest_editor.update()

    async def save_node_edit(self) -> None:
        """Callback invoked by the "done" button on an editor dialog. Fetches
        the editor content to update the target model."""
        node_id = self.current_editor_node_id
        editor_content = await self.editor.run_editor_method("get")
        if "json" in editor_content:
            result = editor_content["json"]
        elif "text" in editor_content:
            try:
                result = json.loads(editor_content["text"])
            except json.JSONDecodeError as e:
                ui.notify(f"Invalid JSON at line {e.lineno} column {e.colno}: {e.msg}", type="negative")
                return
        else:
            ui.notify("Unexpected editor format", type="negative")
            return
        self.model["spec"][node_id] = result
        self.edit_dialog.close()

    async def save_manifest_edit(self) -> None:
        """Callback invoked by the "done" button a manifest editor dialog."""
        manifest_id = self.current_editor_manifest_id
        try:
            current_configuration = yaml.safe_load(self.manifest_editor.value)
            self.model["manifests"][manifest_id]["spec"] = current_configuration
            self.manifest_edit_dialog.close()
        except yaml.MarkedYAMLError as e:
            problem_detail = ""
            if e.problem_mark is not None:
                problem_detail = f"line {e.problem_mark.line + 1}:column {e.problem_mark.column + 1}"
            ui.notify("Problem parsing YAML: {}".format(problem_detail), type="negative")  # noqa: UP032

    async def set_group_config(self, data: ClickEventArguments) -> None:
        """Uses a patch operation to update the current step group config in
        the step's JSON Editor.

        Note: This is a destructive operation and will replace the entire
        current grouping configuration with a new, empty, template config.
        """
        group_config: dict | None
        match data.sender._props:
            case {"id": "grouping_none"}:
                group_config = None
            case {"id": "grouping_fixed"}:
                group_config = {
                    "split_by": "values",
                    "dimension": None,
                    "values": [],
                }
            case {"id": "grouping_query"}:
                group_config = {
                    "split_by": "query",
                    "dataset": None,
                    "dimension": None,
                    "min_groups": 1,
                    "max_size": 0,
                }
            case _:
                raise RuntimeError("no such grouping config option")

        # what follows is a clunky and seemingly redundant way of updating the
        # editor. The issue is that "patch" updates the UI but not the state,
        # and "set" updates the state but not the UI. So we have to "get" the
        # current state, make changes to it, and "set" it back, then "patch"
        # the editor to make it look like it's updated.
        current_configuration = await self.editor.run_editor_method("get")
        current_configuration["json"]["groups"] = group_config

        # The set method updates the state but not the UI
        await self.editor.run_editor_method("set", current_configuration)

        # The patch method updates the UI but not the state
        await self.editor.run_editor_method(
            "patch", [{"op": "replace", "path": "/groups", "value": group_config}]
        )

    async def handle_campaign_name_change(self, e: ValueChangeEventArguments) -> None:
        """Callback wired to the "campaign name" input control."""
        # NOTE this is called on every KEYSTROKE in the text box
        self.campaign_id = uuid5(self.namespace, e.value)

    async def handle_export(self, e: ClickEventArguments) -> None:
        """Callback wired to the "Export" button in the drawer menu."""
        await ui.run_javascript("""window.dispatchEvent(new CustomEvent("canvasExport"));""")

        # Apply current campaign namespace to manifest models.
        for manifest in self.model["manifests"].values():
            manifest["metadata"]["namespace"] = str(self.campaign_id)

        exported_campaign = yaml.dump_all(
            [
                self.model["campaign"],
                *self.model["nodes"],
                *self.model["edges"],
                *self.model["manifests"].values(),
            ]
        )
        ui.download.content(exported_campaign, f"{self.campaign_name}.yaml")

    async def handle_upload(self, e: ClickEventArguments) -> None:
        """Callback wired to the "Upload" button in the drawer menu."""
        self.show_spinner("Saving Campaign...")
        await ui.run_javascript("""window.dispatchEvent(new CustomEvent("canvasExport"));""")

        # Apply current campaign namespace to manifest models.
        for manifest in self.model["manifests"].values():
            manifest["metadata"]["namespace"] = str(self.campaign_id)

        exported_campaign = [
            self.model["campaign"],
            *self.model["nodes"],
            *self.model["edges"],
            *self.model["manifests"].values(),
        ]

        # send list of manifests to loader API
        if not (save_result := await api.put_manifest_list(exported_campaign)):
            ui.notify("One or more manifests failed to save", type="warning")

        self.hide_spinner()

        if save_result:
            ui.navigate.to(f"/campaign/{self.campaign_id}")

    async def handle_exported_canvas(self, data: GenericEventArguments) -> None:
        """Callback wired to the "canvasData" listener, which should be sent
        in response to a "canvasExport" event.
        """

        # the campaign manifest with the current name
        self.model["campaign"]["metadata"]["name"] = self.campaign_name

        canvas_data = data.args.get("data", {})

        # Mapping of canvas node ID to Node data
        canvas_nodes = {node["id"]: node["data"] for node in canvas_data["nodes"]}

        # List of Node Manifest records (START and END are not needed)
        self.model["nodes"] = [
            STEP_MANIFEST_TEMPLATE
            | {
                "metadata": {
                    "name": node["data"]["name"],
                    "namespace": str(self.campaign_id),
                    "kind": node["type"],
                },
                "spec": self.model["spec"].get(node["id"], STEP_SPEC_TEMPLATE),
            }
            for node in canvas_data.get("nodes", {})
            if node["type"] in ["step", "breakpoint"]
        ]

        # the exported edges use the node IDs to describe the source and target
        # so we need to dereference that into the node NAME
        self.model["edges"] = [
            {
                "apiVersion": "io.lsst.cmservice/v1",
                "kind": "edge",
                "metadata": {
                    "name": edge["id"],
                    "namespace": str(self.campaign_id),
                },
                "spec": {
                    "source": canvas_nodes[edge["source"]]["name"],
                    "target": canvas_nodes[edge["target"]]["name"],
                },
            }
            for edge in canvas_data.get("edges", {})
        ]

    async def setup(self, client_: AsyncClient | None = None) -> Any:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.namespace = UUID("dda54a0c-6878-5c95-ac4f-007f6808049e")
        ui.add_head_html("""<script src="/static/cm-canvas-bundle.iife.js"></script>""")
        self.model: CampaignPageModel = {
            "nodes": [],
            "edges": [],
            "spec": {},
            "campaign": {
                "apiVersion": "io.lsst.cmservice/v1",
                "kind": "campaign",
                "metadata": {"name": ""},
                "spec": {"auto_transition": False},
            },
            "manifests": {},
        }
        self.initial_flow_nodes: list[dict] = []
        self.initial_flow_edges: list[dict] = []

        for manifest in await api.get_campaign_manifests():
            self.model["manifests"][manifest["id"]] = {
                "apiVersion": "io.lsst.cmservice/v1",
                "kind": manifest["kind"],
                "metadata": {
                    "name": manifest["name"],
                    "version": 0,
                },
                "spec": manifest["spec"],
            }

        self.campaign_name = "new_campaign"

        return self


class CampaignClonePage(CampaignEditPage):
    """Campaign Edit Page focused on cloning an existing campaign instead of
    creating one from scratch.
    """

    async def setup(self, client_: AsyncClient | None = None, *, clone_campaign_model_from: str = "") -> Any:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.namespace = UUID("dda54a0c-6878-5c95-ac4f-007f6808049e")

        # Add IIFE script for cm-canvas component
        ui.add_head_html("""<script src="/static/cm-canvas-bundle.iife.js"></script>""")

        async with CLIENT_FACTORY.aclient() as client:
            data = await api.describe_one_campaign(client=client, id=clone_campaign_model_from)

        self.campaign_name = data["campaign"]["name"]
        graph: nx.DiGraph = await run.cpu_bound(
            nx.node_link_graph,
            data["graph"],
            edges="edges",  # pyright: ignore[reportCallIssue]
        )
        flow = await nx_to_flow(graph)
        self.initial_flow_nodes = flow["nodes"]
        self.initial_flow_edges = flow["edges"]

        # set up the model with the existing node specs so they can be success-
        # fully edited from the canvas. The nodes and edges are populated at
        # export, so we initialize them to empty lists. The spec lookup is key-
        # ed by the node's flow id which for the simple node view used to init-
        # ialize the flow canvas is the node's `name.version`.
        self.model: CampaignPageModel = {
            "nodes": [],
            "edges": [],
            "spec": {f"{node['name']}.{node['version']}": node["configuration"] for node in data["nodes"]},
            "campaign": {
                "apiVersion": "io.lsst.cmservice/v1",
                "kind": "campaign",
                "metadata": {"name": ""},
                "spec": {"auto_transition": False},
            },
            "manifests": {},
        }

        mandatory_manifests = {"bps", "lsst", "butler", "wms", "site"}
        for manifest in sorted(data["manifests"], key=itemgetter("version"), reverse=True):
            # Manifests for the cloned campaign are reset to version 1 and add-
            # ed to the page's model. The original manifest ID is kept to track
            # it but is not used for eventual serialization of a new object.
            #
            # Only the newest version of any manifest kind available in the
            # original campaign is kept in the new one.
            try:
                mandatory_manifests.remove(manifest["kind"])
            except KeyError:
                continue
            self.model["manifests"][manifest["id"]] = {
                "apiVersion": "io.lsst.cmservice/v1",
                "kind": manifest["kind"],
                "metadata": {
                    "name": manifest["name"],
                    "version": 0,  # The api always increments the version
                },
                "spec": manifest["spec"],
            }

        # Any "missing" manifests could be fetched from the library
        for kind in mandatory_manifests:
            ...

        return self
