"""Page and supporting functions for a Campaign's Edit Mode."""

from copy import deepcopy
from dataclasses import dataclass, field
from enum import IntFlag, auto
from functools import partial
from operator import itemgetter
from typing import Any, Self
from uuid import uuid4, uuid5

import networkx as nx
import yaml
from httpx import AsyncClient
from nice_dialogs.dialogs import CronEditorDialog, UploadFileDialog
from nicegui import app, run, ui
from nicegui.elements.upload_files import FileUpload, SmallFileUpload
from nicegui.events import ClickEventArguments, GenericEventArguments, ValueChangeEventArguments

from lsst.cmservice.models.api.schedules import ScheduleManifest
from lsst.cmservice.models.db.schedules import CreateManifestTemplate, CreateSchedule
from lsst.cmservice.models.enums import DEFAULT_NAMESPACE, ManifestKind
from lsst.cmservice.models.lib.parsers import as_snake_case
from lsst.cmservice.models.lib.yaml import str_representer

from .. import api
from ..components.button import ToggleButton
from ..components.dialog import EditorContext, NewManifestEditorDialog, NewStepEditorDialog
from ..components.expression import ExpressionEditorDialog
from ..lib.canvas import nx_to_flow
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import MANIFEST_KIND_ICONS
from ..lib.models import STEP_MANIFEST_TEMPLATE
from ..settings import settings
from .common import CMPage, CMPageData

# Apply a custom str representer/parser to the YAML library to format multi-
# line strings using YAML `|` syntax.
yaml.add_representer(str, str_representer)


class PageFlags(IntFlag):
    ALLOW_SAVE = auto()
    ALLOW_EXPORT = auto()
    ALLOW_SCHEDULE = auto()
    SCHEDULING_MODE = auto()


# TODO replace with a pydantic model
@dataclass
class CampaignPageModel(CMPageData):
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    spec: dict[str, dict[str, Any]] = field(default_factory=dict)
    campaign: dict[str, Any] = field(default_factory=dict)
    manifests: dict[str, Any] = field(default_factory=dict)
    schedule_info: dict[str, Any] = field(default_factory=dict)
    flags: PageFlags = field(default_factory=lambda: PageFlags(0))


class CampaignEditPage(CMPage[CampaignPageModel]):
    """The campaign edit view has a ribbon for accessing and editing
    Manifests and a canvas area for manipulating a graph. Each node in the
    graph will have an edit button.

    No objects are written to the database until the SAVE button in the
    menu drawer is used. Alternately, the EXPORT button will allow a down-
    load of the campaign in YAML format.
    """

    def initialize_model(self) -> None:
        """Initializes the page model with an empty campaign."""
        self.model = CampaignPageModel(
            campaign=deepcopy(STEP_MANIFEST_TEMPLATE) | {"kind": "campaign", "metadata": {"name": ""}},
        )

    async def edit_campaign_name(self) -> None:
        """A row of elements for editing high-level campaign details, such as
        the name.
        """
        with ui.row().classes("shrink-0 p-1 w-full items-center"):
            ui.input(label="Campaign Name", on_change=self.handle_campaign_name_change).bind_value(
                self, "campaign_name"
            ).classes("w-48").props("debounce=1000")

            with (
                ui.input(
                    label="Cron Expression",
                    value="0 0 1-7 * SUN",  # midnight on first sunday of the month
                    validation={
                        "Cron too frequent": lambda c: not c.startswith("*"),
                    },
                )
                .classes("pb-0")
                .props("readonly") as self.cron_expression_input
            ):
                ui.button(icon="schedule", color="accent", on_click=self.handle_cron_dialog).props(
                    "flat"
                ).tooltip("Edit cron")

            self.campaign_template_name_format = (
                ui.input(
                    label="Name Format",
                    value="%Y%m%d",
                )
                .props('input-class="font-mono"')
                .tooltip(
                    "A `strftime` format string for appending runtime tokens to generated campaign names."
                )
            )

            self.expressions_dialog_button = (
                ui.button(icon="calculate", on_click=self.handle_expressions_dialog)
                .props("fab-mini")
                .tooltip("Edit Template Expressions")
            )

            self.auto_start_scheduled_campaign = ui.switch(
                text="Auto-start Scheduled Campaign",
                value=False,
            ).tooltip("Whether new campaigns created from this schedule should be RUNNING by default.")

    @ui.refreshable_method
    async def edit_campaign_manifests(self) -> None:
        """Renders an expansion group containing cards for editing campaign
        manifests.
        """
        with (
            ui.expansion(
                "Configuration Manifests", icon="extension", caption="Edit or add configuration manifests"
            ).classes("w-full"),
            ui.row().classes("w-full flex-nowrap gap-4 py-2 overflow-x-auto items-center"),
        ):
            for manifest_id, manifest in self.model.manifests.items():
                with ui.card().classes("m-1 p-1 shrink-1"):
                    with ui.card_section():
                        with ui.column():
                            ui.chip(text=manifest["kind"].upper(), color="accent").classes("text-xs").props(
                                "outline square"
                            ).bind_icon_from(MANIFEST_KIND_ICONS, manifest["kind"]).tooltip(manifest_id)
                            ui.input(label="Manifest Name").bind_value(
                                self.model.manifests[manifest_id]["metadata"], "name"
                            ).classes("text-sm")
                    with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                        ui.space()
                        ToggleButton(color="dark").props("style: flat").tooltip(
                            "Set as default manifest for campaign"
                        )
                        ui.button(
                            icon="edit",
                            color="dark",
                            on_click=partial(self.handle_manifest_edit, manifest_id),
                        ).props("style: flat").tooltip("Edit Manifest Configuration")
            ui.space()
            ui.button(icon="add", on_click=self.handle_manifest_edit).props("fab color=accent").tooltip(
                "Add a new manifest"
            )

    @ui.refreshable_method
    async def create_campaign_canvas(self) -> None:
        """A section containing a Canvas component for editing a campaign
        graph.
        """
        ui.run_javascript("""if (window.flowInstance?.cleanup) {{ window.flowInstance.cleanup(); }}""")

        with (
            ui.element("div")
            .props("id=canvas-container")
            .classes("flex-1 w-full border-1 border-gray-500")
            .style("isolation: isolate; contain: layout style paint;")
        ):
            ui.run_javascript(f"""
                window.flowInstance = initializeFlow("canvas-container", {{
                    nodes: {self.initial_flow_nodes},
                    edges: {self.initial_flow_edges},
                    onClick: (data) => emitEvent("edit", data)
                }});
            """)

    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """
        await self.edit_campaign_name()
        await self.edit_campaign_manifests()
        await self.create_campaign_canvas()

        # setup listeners
        ui.on("canvasExported", self.handle_exported_canvas)
        ui.on("edit", self.handle_node_edit)

        ui.run_javascript("""
            window.addEventListener("canvasExported", (e) => {
                emitEvent("canvasExported", e.detail);
            });
        """)

        # setup bindings
        self.cron_expression_input.bind_visibility_from(
            self,
            ("model", "flags"),
            backward=lambda v: PageFlags.SCHEDULING_MODE in v,
            strict=False,
        ).bind_value(
            self,
            ("model", "schedule_info", "cron"),
            strict=False,
        )
        self.expressions_dialog_button.bind_visibility_from(
            self,
            ("model", "flags"),
            backward=lambda v: PageFlags.SCHEDULING_MODE in v,
            strict=False,
        )
        self.save_button.bind_enabled_from(
            self,
            ("model", "flags"),
            backward=lambda v: PageFlags.SCHEDULING_MODE not in v,
            strict=False,
        )
        self.scheduling_switch.bind_value_to(
            self,
            ("model", "flags"),
            strict=False,
            forward=lambda v: (
                self.model.flags | PageFlags.SCHEDULING_MODE
                if v
                else self.model.flags & ~PageFlags.SCHEDULING_MODE
            ),
        )
        # TODO bind enabled from multiple conditions, including "valid" cron
        self.save_schedule_button.bind_enabled_from(
            self,
            ("scheduling_switch", "value"),
            strict=False,
        )
        self.auto_start_scheduled_campaign.bind_visibility_from(
            self,
            ("model", "flags"),
            backward=lambda v: PageFlags.SCHEDULING_MODE in v,
            strict=False,
        ).bind_value(self, ("model", "schedule_info", "auto_start"), strict=False)
        self.campaign_template_name_format.bind_visibility_from(
            self,
            ("model", "flags"),
            backward=lambda v: PageFlags.SCHEDULING_MODE in v,
            strict=False,
        ).bind_value(self, ("model", "schedule_info", "name_format"), strict=False)

    def drawer_contents(self) -> None:
        """Right-side menu drawer contents rendered in a ui.column."""
        self.save_button = ui.button("Save", icon="save", on_click=self.handle_save).classes("w-50")
        ui.button("Export", icon="save_alt", on_click=self.handle_export).classes("w-50")
        ui.button("Import", icon="file_upload", on_click=self.handle_import).classes("w-50")
        ui.separator()
        self.scheduling_switch = ui.switch("Enable Scheduling Mode").on_value_change(self.toggle_drawer)
        self.save_schedule_button = ui.button(
            "Schedule", icon="update", on_click=self.handle_schedule_save
        ).classes("w-50")

    async def footer_contents(self) -> None:
        ui.label().classes("text-xs").bind_text_from(self, "campaign_id", strict=False)

    async def handle_node_edit(self, data: GenericEventArguments) -> None:
        """Callback target for "edit" events emitted by nodes on the canvas."""
        step_id, step_name = data.args

        # Update the metadata name of any held model
        if (node := self.model.spec.get(step_id)) is not None:
            node["metadata"]["name"] = step_name

        ctx = EditorContext(
            page=self,
            namespace=str(self.namespace),
            name=step_name,
            kind="step",
            allow_name_change=False,
            name_validators=[],  # TODO add name validator to check dups
        )
        dialog = NewStepEditorDialog(
            ctx,
            title="New Step Editor",
            initial_model=node,
        )
        result: dict[str, Any] | None = await dialog
        dialog.clear()
        if result is None:
            return None
        # clean up the manifest in a step-specific way
        _ = result.get("metadata", {}).pop("uuid", None)
        self.model.spec[step_id] = result

    async def handle_manifest_edit(self, manifest_id: str | None = None) -> None:
        """Callback for editing or creating a campaign manifest.

        New manifests are given a UUID4 identifier for tracking in the page
        model. Existing manifests retain whatever ID they were assigned when
        first added to the model.
        """
        ctx = EditorContext(
            page=self,
            namespace=str(self.namespace),
            name_validators=["validate_new_manifest_name"],
        )
        manifest_model: dict | None
        if manifest_id is None:
            ctx.uuid = str(uuid4())
            ctx.allow_kind_change = True
            ctx.allow_name_change = True
            manifest_model = None
        else:
            ctx.uuid = manifest_id
            ctx.name = self.model.manifests[manifest_id]["metadata"]["name"]
            ctx.kind = self.model.manifests[manifest_id]["kind"]
            ctx.allow_name_change = False
            ctx.allow_kind_change = False
            manifest_model = self.model.manifests.get(ctx.uuid, {})

        dialog = NewManifestEditorDialog(
            ctx,
            title="Manifest Editor",
            initial_model=manifest_model,
        )

        result = await dialog
        dialog.clear()
        await self.save_manifest_edit(result)

    async def save_manifest_edit(self, data: dict | None) -> None:
        """Callback invoked to save an edited Manifest to the page model."""
        # manifest_id is used here only for tracking manifests in the page's
        # model hierarchy and does not need to be the same as the manifest's
        # eventual database ID
        if data is None:
            return None

        if (manifest_id := data["metadata"].pop("uuid", None)) is None:
            ui.notify(
                "An error occurred saving the manifest: the manifest does not have an ID.",
                type="negative",
            )
            return

        # reduce the None/nulls from the spec
        data["spec"] = {k: v for k, v in data["spec"].items() if v is not None}
        self.model.manifests[manifest_id] = data
        await self.edit_campaign_manifests.refresh()

    async def handle_campaign_name_change(self, e: ValueChangeEventArguments) -> None:
        """Callback wired to the "campaign name" input control."""
        self.campaign_name = as_snake_case(e.value)
        self.campaign_id = uuid5(self.namespace, self.campaign_name)

    async def handle_export(self, e: ClickEventArguments) -> None:
        """Callback wired to the "Export" button in the drawer menu."""
        await ui.run_javascript("""window.dispatchEvent(new CustomEvent("canvasExport"));""")
        to_export = [
            self.model.campaign,
            *self.model.nodes,
            *self.model.edges,
            *self.model.manifests.values(),
        ]
        # if in scheduling mode, export the schedule as an additional manifest
        if PageFlags.SCHEDULING_MODE in self.model.flags:
            to_export.append(
                ScheduleManifest(
                    kind=ManifestKind.schedule,
                    spec=self.model.schedule_info,
                    metadata={},  # pyright: ignore[reportCallIssue]
                ).model_dump(by_alias=True)
            )

        exported_campaign = yaml.dump_all(to_export)

        ui.download.content(exported_campaign, f"{self.campaign_name}.yaml")

    async def handle_import(self, e: ClickEventArguments) -> None:
        """Callback wired to the "Import" button in the drawer menu.

        This callback uses a file-upload dialog to receive a YAML file from the
        user. The current page model is replaced by the contents of the loaded
        YAML file, allowing the user to make further edits, save, or re-export
        the campaign.
        """
        self.show_spinner("Importing Campaign...")
        upload = await UploadFileDialog(
            dialog_title="Import CM Campaign",
            allowed_file_types=[
                "application/yaml",
                "application/x-yaml",
                "text/yaml",
                "text/x-yaml",
                ".yaml",
                ".yml",
            ],
            max_file_size=settings.max_upload_size,
        )
        if upload is not None:
            await self.apply_import_to_model(upload)
        else:
            self.hide_spinner()
            return None

    async def handle_save(self, e: ClickEventArguments) -> None:
        """Callback wired to the "Save" button in the drawer menu.

        This callback loads all campaign manifests available in the current
        page model via REST API, then redirects to the Campaign Overview page
        for the newly saved campaign.
        """
        self.show_spinner("Saving Campaign...")
        await ui.run_javascript("""window.dispatchEvent(new CustomEvent("canvasExport"));""")

        exported_campaign = [
            self.model.campaign,
            *self.model.nodes,
            *self.model.edges,
            *self.model.manifests.values(),
        ]

        # send list of manifests to loader API
        if not (save_result := await api.put_manifest_list(exported_campaign)):
            ui.notify("One or more manifests failed to save", type="warning")

        self.hide_spinner()

        if save_result:
            ui.navigate.to(f"/campaign/{self.campaign_id}")

    async def handle_schedule_save(self, e: ClickEventArguments) -> None:
        """Save the current campaign as a schedule with manifest templates."""
        # Use export logic to get list of manifests as YAML
        # Instead of downloading a file, assemble a Schedule model and POST
        # to the schedules API
        self.show_spinner("Scheduling Campaign...")
        await ui.run_javascript("""window.dispatchEvent(new CustomEvent("canvasExport"));""")

        exported_campaign = [
            self.model.campaign,
            *self.model.nodes,
            *self.model.edges,
            *self.model.manifests.values(),
        ]

        # Create a Schedule object
        schedule = CreateSchedule(
            name=f"schedule-{self.campaign_name}-{uuid4().hex[0:8]}",
            cron=self.model.schedule_info["cron"],
            metadata_={
                "owner": self.username,
            },
            configuration={
                "auto_start": self.model.schedule_info["auto_start"],
                "expressions": self.model.schedule_info["expressions"],
                "date_format": self.model.schedule_info["date_format"],
            },
            is_enabled=False,
            templates=[],
        )

        # Create a ManifestTemplate for each manifest
        for manifest in exported_campaign:
            # add each manifest as a CreateManifestTemplate to the templates
            schedule.templates.append(
                CreateManifestTemplate(
                    name=manifest["metadata"]["name"],
                    kind=manifest["kind"],
                    manifest=yaml.safe_dump(manifest, explicit_start=True),
                )
            )

        # API POST new schedule
        if not (save_result := await api.post_new_schedule(schedule)):
            ui.notify(
                "A problem occurred saving the new schedule. "
                "Try again or use export to save an offline copy.",
                type="warning",
            )

        self.hide_spinner()

        if save_result:
            ui.navigate.to("/schedules")

    async def handle_exported_canvas(self, data: GenericEventArguments) -> None:
        """Callback wired to the "canvasData" listener, which should be sent
        in response to a "canvasExport" event.

        This event is sent when the Save or Export buttons callback are invoked
        in order to apply current canvas design to the page model. As the model
        is updated, the current campaign name/id is applied to each manifest's
        namespace.
        """

        # the campaign manifest with the current name
        self.model.campaign["metadata"]["name"] = self.campaign_name

        canvas_data = data.args.get("data", {})

        # Mapping of canvas node ID to Node data
        canvas_nodes = {node["id"]: node["data"] for node in canvas_data["nodes"]}

        # List of Node Manifest records (START and END are not needed)
        # Any saved step manifests are applied to the template, otherwise the
        # metadata is constructed.
        self.model.nodes = [
            deepcopy(STEP_MANIFEST_TEMPLATE)
            | self.model.spec.get(
                node["id"], {"metadata": {"name": node["data"]["name"], "kind": node["type"]}}
            )
            for node in canvas_data.get("nodes", [])
            if node["type"] in ["step", "breakpoint"]
        ]

        # Apply current campaign namespace to manifest models and nodes.
        for manifest in self.model.manifests.values():
            manifest["metadata"]["namespace"] = str(self.campaign_id)
        for node in self.model.nodes:
            node["metadata"]["namespace"] = str(self.campaign_id)

        # the exported edges use the node IDs to describe the source and target
        # so we need to dereference that into the node NAME
        self.model.edges = [
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
        ...

    async def handle_expressions_dialog(self, e: ClickEventArguments) -> None:
        """Creates an editor dialog for custom template expressions."""
        expressions_dialog = ExpressionEditorDialog(
            with_expressions=self.model.schedule_info.get("expressions", {})
        )
        expressions = await expressions_dialog
        if expressions is not None:
            self.model.schedule_info["expressions"] = expressions
        expressions_dialog.clear()

    async def handle_cron_dialog(self, e: ClickEventArguments) -> None:
        """Creates a cron editor dialog for the current cron string."""
        cron_dialog = CronEditorDialog()
        cron_dialog.reset(self.model.schedule_info.get("cron"))
        cron_str = await cron_dialog
        if cron_str is not None:
            self.model.schedule_info["cron"] = cron_str
        cron_dialog.clear()

    async def validate_new_manifest_name(self, data: str | None, ctx: EditorContext) -> str | None:
        """Validates the name of a new manifest by checking against any current
        manifest names in the current known model. This does not perform API
        or database IO.

        If the manifest name cannot be changed (because the input is disabled
        and therefore read-only), no validation occurs. This is mostly to min-
        imize spurious errors when the value is set programatically.
        """
        manifest_kind = ctx.kind
        if not ctx.allow_name_change:
            return None
        if data is None:
            return "A name is required"
        if manifest_kind is None:
            return "A manifest kind must be set"

        # Since we can't use an ID to test for uniqueness, we need to check
        # the actual metadata attributes in the model
        if (manifest_kind, data) in [
            (v["kind"], v["metadata"]["name"]) for v in self.model.manifests.values()
        ]:
            return "Name must be unique by kind in the campaign"
        return None

    async def setup(self, client_: AsyncClient | None = None) -> Any:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.namespace = DEFAULT_NAMESPACE
        self.initialize_model()
        self.initial_flow_nodes: list[dict] = []
        self.initial_flow_edges: list[dict] = []

        for manifest in await api.get_campaign_manifests():
            # Library manifests are reassigned a new UUID for tracking in the
            # page model
            self.model.manifests[str(uuid4())] = {
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

    async def apply_import_to_model(self, upload: FileUpload) -> None:
        """Applies an imported YAML file upload to the current page model."""

        # clear the current page model
        self.initialize_model()
        self.initial_flow_nodes = []
        self.initial_flow_edges = []

        # NOTE: the uploaded file is in a memory buffer, so this is not really
        # an IO-bound operation. Because pyyaml doesn't have async capabilities
        # we load the whole file on a thread and iterate the list result.
        contents = await upload.read()
        try:
            # Each imported manifest is shaped and added to the page model's
            # `spec` dictionary and canvas components. Some metadata values are
            # removed so they do not leak into new campaigns.
            manifest_list = await run.io_bound(lambda: list(yaml.safe_load_all(contents)))
            # Apply the imported manifests in campaign -> * -> edge order
            for manifest in sorted(
                manifest_list,
                key=lambda m: (m["kind"] == "campaign", m["kind"] != "edge"),
                reverse=True,
            ):
                match manifest["kind"]:
                    case "campaign":
                        self.campaign_name = manifest["metadata"].pop("name")
                    case "edge":
                        self.initial_flow_edges.append(
                            {
                                "id": manifest["metadata"]["name"],
                                "source": f"""{manifest["spec"]["source"]}.1""",
                                "target": f"""{manifest["spec"]["target"]}.1""",
                            }
                        )
                    case "node":
                        # Add the imported node to the model's spec and the
                        # canvas nodes
                        manifest["metadata"].pop("namespace", None)
                        node_id = f"{manifest['metadata']['name']}.1"
                        self.model.spec[node_id] = manifest

                        self.initial_flow_nodes.append(
                            {
                                "id": node_id,
                                "position": {"x": 0, "y": 0},
                                "data": {"name": manifest["metadata"]["name"]},
                                "type": manifest["metadata"]["kind"],
                            }
                        )
                    case "lsst" | "butler" | "wms" | "site" | "bps":
                        manifest["metadata"].pop("namespace", None)
                        if (manifest_id := manifest["metadata"].pop("id", None)) is None:
                            manifest_id = str(uuid4())  # FIXME what is the real uuid
                        self.model.manifests[manifest_id] = manifest
                    case "schedule":
                        self.model.schedule_info = manifest["spec"]
                        self.scheduling_switch.value = True
                        self.scheduling_switch.disable()
                        self.scheduling_switch.tooltip(
                            "Can't disable scheduling mode when importing a scheduled campaign."
                        )
                    case _:
                        # NOTE this should be unreachable, but if we do end up
                        # here, we gracefully fall through.
                        pass
        except yaml.YAMLError:
            ui.notify("Could not load YAML from uploaded file.", color="negative")
        except KeyError as e:
            ui.notify(e)

        # refresh page components
        await self.edit_campaign_manifests.refresh()
        await self.create_campaign_canvas.refresh()
        self.hide_spinner()


class CampaignClonePage(CampaignEditPage):
    """Campaign Edit Page focused on cloning an existing campaign instead of
    creating one from scratch.
    """

    async def setup(
        self,
        client_: AsyncClient | None = None,
        *,
        clone_campaign_model_from: str = "",
        clone_campaign_schedule_from: str = "",
    ) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.namespace = DEFAULT_NAMESPACE

        async with CLIENT_FACTORY.aclient() as client:
            if clone_campaign_model_from:
                data = await api.describe_one_campaign(client=client, id=clone_campaign_model_from)
            elif clone_campaign_schedule_from:
                return await self.setup_from_schedule(clone_campaign_schedule_from)

        self.campaign_name = data["campaign"]["name"]
        # FIXME this doesn't need to be cpu_bound (process), io_bound (thread)
        # is probably fine
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
        # FIXME the metadata of prepared steps should not be allowed to leak
        self.model = CampaignPageModel(
            spec={
                f"{node['name']}.{node['version']}": (
                    deepcopy(STEP_MANIFEST_TEMPLATE)
                    | {
                        "metadata": node["metadata"] | {"name": node["name"], "kind": node["kind"]},
                        "spec": node["configuration"],
                    }
                )
                for node in data["nodes"]
            },
            campaign=(deepcopy(STEP_MANIFEST_TEMPLATE) | {"kind": "campaign", "metadata": {"name": ""}}),
        )

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
            self.model.manifests[manifest["id"]] = deepcopy(STEP_MANIFEST_TEMPLATE) | {
                "kind": manifest["kind"],
                "metadata": {
                    "name": manifest["name"],
                    "uuid": manifest["id"],
                    "version": 0,  # The api always increments the version
                },
                "spec": manifest["spec"],
            }

        # TODO Any "missing" manifests could be fetched from the library
        for kind in mandatory_manifests:
            ...

        return self

    async def setup_from_schedule(self, schedule_id: str) -> Self:
        """Page setup method when importing a stored schedule.

        Notes
        -----
        - The stored schedule manifest templates MUST be stored with an
        explicit start (`---`). This method uses a naive string-join that
        assumes this is the case.
        """

        schedule: CreateSchedule | None
        # FIXME the client needs to be connected before accessing tab storage
        if (schedule := app.storage.tab.pop("schedule", None)) is None:
            schedule_ = await anext(api.get_schedule_summary(schedule_id))
            schedule = CreateSchedule.model_validate(schedule_)

        templates = api.get_schedule_templates(schedule_id=schedule_id)

        # Create an "export" collection YAML documents.
        yaml_import: str = "".join([template.manifest async for template in templates])
        yaml_import += yaml.safe_dump(
            ScheduleManifest(
                kind=ManifestKind.schedule,
                spec=schedule.configuration,
                metadata={},  # pyright: ignore[reportCallIssue]
            ).model_dump(by_alias=True),
            explicit_start=True,
        )

        # create a "SmallFileUpload" container for the schedule parts
        # as though it had been imported from a YAML
        schedule_import = SmallFileUpload(
            name="schedule.yaml",
            content_type="application/yaml",
            _data=yaml_import.encode("utf-8"),
        )
        await self.apply_import_to_model(schedule_import)

        return self
