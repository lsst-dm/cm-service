# ruff: disable[ERA001, W505]

from typing import Any, Self, assert_never

from httpx import AsyncClient
from nice_dialog.dialogs.cron_editor import CronEditorDialog
from nicegui import run, ui
from nicegui.events import GenericEventArguments
from pydantic_extra_types.cron import CronStr

from lsst.cmservice.models.db.schedules import ManifestTemplateBase

from ..api.schedules import get_schedule_summary, get_schedule_templates
from ..components import storage
from ..components.dialog import ScheduleEditorDialog
from .common import CMPage, CMPageModel


class ScheduleOverviewPageModel(CMPageModel):
    """ "Page data model for scheduling overview page.

    Attributes
    ----------
    schedules: dict[str, dict[str, Any]
        A mapping of schedule IDs to a schedule instance. Each schedule in the
        mapping will be shown on the scheduling overview table modulo any active
        filtering. Each value is a dict representation of the database Schedule
        record.

    active_schedule: str
        The string ID of an "active" schedule. The active schedule is one that
        is the target of editing operations.

    active_templates: list[dict[str, Any]]
        A list of templates associated with the "active schedule", lazily-
        loaded when needed.
    """

    schedules: dict[str, dict[str, Any]]
    active_templates: list[ManifestTemplateBase]
    active_schedule: str  # id of schedule most recently accessed


class ScheduleOverviewPage(CMPage[ScheduleOverviewPageModel]):
    """Displays currently enrolled CM Schedules in a table layout.

    Available filters by owner, ...
    """

    async def setup(self, client_: AsyncClient | None = None) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        if client_ is None:
            raise RuntimeError("Campaign Overview page setup requires an httpx client")

        self.show_spinner()
        self.model: ScheduleOverviewPageModel = {
            "schedules": {},
            "active_templates": [],
            "active_schedule": "",
        }
        storage.initialize_client_storage()
        # client_state: storage.ClientStorageModel = app.storage.client["state"]

        # Default filters
        # active_filters = app.storage.client["state"].user.active_filters
        # active_filters.add("ignored")
        # app.storage.client["state"].user.active_filters = active_filters

        async for schedule in await run.io_bound(get_schedule_summary, client=client_):
            # TODO check favorites / filters
            # Add each schedule to the page model, indexed by its ID.
            self.model["schedules"][schedule["id"]] = schedule
            self.model["schedules"][schedule["id"]]["metadata"]["dirty"] = {}

        self.cron_dialog = CronEditorDialog()
        return self

    def drawer_contents(self) -> None: ...

    @ui.refreshable_method
    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """

        self.table_content = ui.element("div").classes(
            "w-full h-full pt-[0.5rem] pb-[0.5rem] overflow-y-auto"
        )
        await self.new_schedule_controls()
        # with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
        #     ui.button(icon="add", on_click=lambda: ui.navigate.to("...")).props("fab color=accent")

        await self.create_schedule_table()
        self.hide_spinner()

    @ui.refreshable_method
    async def create_schedule_table(self) -> None:
        """Renders a table of schedules"""
        columns: list[dict[str, Any]] = [
            {"name": "id", "label": "ID", "field": "id", "classes": "hidden", "headerClasses": "hidden"},
            {
                "name": "name",
                "label": "Name",
                "field": "name",
                "sortable": True,
                ":classes": "(row) => row.classes",
            },
            {
                "name": "owner",
                "label": "Owner",
                "field": "owner",
                "sortable": True,
                ":classes": "(row) => row.classes",
            },
            {
                "name": "cron",
                "label": "Cron Expression",
                "field": "cron",
                "sortable": False,
                ":classes": '(row) => row.classes + " " + row.cron_extra',
            },
            {
                "name": "status",
                "label": "Status",
                "field": "status",
                "sortable": True,
                "align": "center",
                ":classes": '(row) => row.classes + " " + row.status_extra',
            },
            {
                "name": "next",
                "label": "Next Run",
                "field": "next",
                "sortable": True,
                ":classes": "(row) => row.classes",
            },
            {"name": "actions", "label": "Actions", "field": "actions"},
        ]
        with self.table_content:
            self.schedules_table = ui.table(columns=columns, rows=[]).classes("w-full h-full overflow-auto")

        await self.update_table_rows()
        with self.schedules_table.add_slot("body-cell-actions"):
            with self.schedules_table.cell("actions"):
                await self.get_schedule_actions()

    async def get_schedule_actions(self) -> None:
        """Creates action buttons for a schedule table cell"""
        ui.button(
            icon="preview",
            color="dark",
        ).props("flat round size=sm").tooltip("View").on(
            "click",
            js_handler="() => emit(props.row.id, 'preview')",
            handler=self.handle_schedule_action,
        )
        ui.button(
            icon="edit",
            color="dark",
        ).props("flat round size=sm").tooltip("Edit").on(
            "click",
            js_handler="() => emit(props.row.id, 'edit')",
            handler=self.handle_schedule_action,
        )
        ui.button(
            icon="save",
            color="dark",
        ).props("flat round size=sm").tooltip("Save").on(
            "click",
            js_handler="() => emit(props.row.id, 'save')",
            handler=self.handle_schedule_action,
        )

    async def handle_schedule_action(self, data: GenericEventArguments) -> None:
        """Callback for action buttons on schedule rows"""
        # Data input should include the node id, and we could defer dialog
        # behaviors to this callback to simplify the logic in the Node card
        target, action = data.args
        schedule = self.model["schedules"][target]

        match action:
            case "cron":
                # Lookup current cron expression in model and set dialog
                old_cron = schedule["cron"]
                self.cron_dialog.reset(old_cron)
                if (new_cron := await self.cron_dialog) is not None:
                    # Update model with new cron and refresh table
                    schedule["cron"] = new_cron
                    schedule["metadata"]["dirty"] |= {"cron": "bg-blue-200"}
                    await self.update_table_rows()

            case "toggle":
                schedule["is_enabled"] = not schedule["is_enabled"]
                schedule["metadata"]["dirty"] |= {"status": "bg-blue-200"}

            case "preview":
                if schedule["id"] != self.model["active_schedule"]:
                    self.model["active_templates"] = [
                        t async for t in get_schedule_templates(schedule_id=schedule["id"])
                    ]
                scheduler_preview = ScheduleEditorDialog(
                    dialog_title=schedule["name"], schedule=schedule, templates=self.model["active_templates"]
                )
                await scheduler_preview
                scheduler_preview.clear()

            case "edit":
                ...
            case "save":
                # Pop the "dirty" metadata flags and make a db update
                schedule["metadata"].pop("dirty")
                ...
                schedule["metadata"]["dirty"] = {}
            case _ as unreachable:
                assert_never(unreachable)

        # we could try to check for any dirty state...or just refresh on every action
        await self.update_table_rows()
        ui.notify(f"{action}: {target}")

    async def update_table_rows(self) -> None:
        self.schedules_table.rows = [
            {
                "id": schedule["id"],
                "name": schedule["name"],
                "cron": schedule["cron"],
                "status": schedule["is_enabled"],
                "owner": schedule["metadata"]["owner"],
                "next": CronStr(schedule["cron"]).next_run,
                "actions": None,
                "classes": "",
                "cron_extra": schedule["metadata"].get("dirty", {}).get("cron", ""),
                "status_extra": schedule["metadata"].get("dirty", {}).get("status", ""),
            }
            for schedule in sorted(
                self.model["schedules"].values(), key=lambda x: x.get("next_run_at", 0), reverse=False
            )
        ]

        # Custom cron schedule display as a clickable badge-button
        with self.schedules_table.add_slot("body-cell-cron"):
            with self.schedules_table.cell("cron"):
                ui.badge(color="grey").props("""
                    :label="props.value"
                """).classes("cursor-pointer").on(
                    "click",
                    js_handler="() => emit(props.row.id, 'cron')",
                    handler=self.handle_schedule_action,
                ).tooltip("Edit Schedule")

        # Status toggle button
        with self.schedules_table.add_slot("body-cell-status"):
            with self.schedules_table.cell("status"):
                ui.button().props("""
                    flat round size=sm
                    :color="props.value ? 'positive' : 'negative'"
                    :icon="props.value ? 'toggle_on' : 'toggle_off'"
                """).on(
                    "click",
                    js_handler="() => emit(props.row.id, 'toggle')",
                    handler=self.handle_schedule_action,
                ).tooltip("Enable Schedule")

    async def new_schedule_controls(self) -> None:
        with ui.element("div").classes("w-full h-full pt-[0.5rem] pb-[0.5rem] overflow-y-auto"):
            ui.label("Add a new schedule")
