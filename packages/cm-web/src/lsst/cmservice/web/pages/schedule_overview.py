from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Self, assert_never

from httpx import AsyncClient
from nice_dialogs.dialogs import ConfirmationDialog, CronEditorDialog, DatetimePickerDialog
from nicegui import app, ui
from nicegui.events import ClickEventArguments, GenericEventArguments
from pydantic_extra_types.cron import CronStr

from lsst.cmservice.models.api.schedules import ScheduleUpdate
from lsst.cmservice.models.db.schedules import CreateManifestTemplate, CreateSchedule

from ..api import schedules
from ..components import storage
from ..components.dialog import ScheduleReviewDialog
from .common import CMPage, CMPageModel


class ScheduleOverviewPageModel(CMPageModel):
    """ "Page data model for scheduling overview page.

    Attributes
    ----------
    schedules: dict[str, dict[str, Any]
        A mapping of schedule IDs to a schedule instance. Each schedule in the
        mapping will be shown on the scheduling overview table modulo any
        active filtering. Each value is a dict representation of the database
        Schedule record.

    active_schedule: str
        The string ID of an "active" schedule. The active schedule is one that
        is the target of editing operations.

    active_templates: list[dict[str, Any]]
        A list of templates associated with the "active schedule", lazily-
        loaded when needed.
    """

    schedules: dict[str, CreateSchedule]
    active_templates: list[CreateManifestTemplate]
    active_schedule: str  # id of schedule most recently accessed
    active_starts_after_filter: datetime


class ScheduleOverviewPage(CMPage[ScheduleOverviewPageModel]):
    """Displays currently enrolled CM Schedules in a table layout."""

    async def setup(self, client_: AsyncClient | None = None) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.show_spinner()
        self.model: ScheduleOverviewPageModel = {
            "schedules": {},
            "active_templates": [],
            "active_schedule": "",
            "active_starts_after_filter": datetime.now(tz=UTC),
        }
        storage.initialize_client_storage()

        async for schedule in schedules.get_schedule_summary():
            # Add each schedule to the page model, keyed by its ID.
            self.model["schedules"][schedule["id"]] = CreateSchedule.model_validate(schedule)

        self.cron_dialog = CronEditorDialog()
        return self

    def drawer_contents(self) -> None:
        """Right-side drawer contents, mostly filter options for the schedules
        table.
        """
        self.owner_filter = (
            ui.select(
                options=[],
                with_input=True,
                multiple=True,
                label="Filter by Owner",
                on_change=self.update_table_rows,
            )
            .classes("w-full")
            .props("use-chips")
        )

        with ui.input(label="Starts After").classes("w-full").props("readonly") as self.starts_after_filter:
            ui.button(icon="schedule", color="accent", on_click=self.handle_starts_after_picker).props("flat")

    @ui.refreshable_method
    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """
        # Apply bindings to page model
        self.starts_after_filter.bind_value_from(
            self,
            ("model", "active_starts_after_filter"),
            backward=lambda v: v.strftime("%c"),
            strict=False,
        )

        # update the owner-filter options dropdown
        self.owner_filter.set_options(
            list({s.metadata_.get("owner", "root") for s in self.model["schedules"].values()})
        )

        self.table_content = ui.element("div").classes(
            "w-full h-full pt-[0.5rem] pb-[0.5rem] overflow-y-auto"
        )
        await self.new_schedule_controls()
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
                "label": "Enabled",
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
            icon="zoom_in",
            color="dark",
        ).props("flat round size=sm").on(
            "click",
            js_handler="() => emit(props.row.id, 'preview')",
            handler=self.handle_schedule_action,
        ).tooltip("Preview")
        ui.button(
            icon="edit",
            color="dark",
        ).props("flat round size=sm").on(
            "click",
            js_handler="() => emit(props.row.id, 'edit')",
            handler=self.handle_schedule_action,
        ).tooltip("Edit")
        ui.button(
            icon="play_arrow",
            color="dark",
        ).props("flat round size=sm").on(
            "click",
            js_handler="() => emit(props.row.id, 'one_shot')",
            handler=self.handle_schedule_action,
        ).tooltip("Run Now")
        ui.button(
            icon="delete",
            color="dark",
        ).props("flat round size=sm").on(
            "click",
            js_handler="() => emit(props.row.id, 'delete')",
            handler=self.handle_schedule_action,
        ).tooltip("Delete")

    async def handle_schedule_action(self, data: GenericEventArguments) -> None:
        """Callback for action buttons on schedule rows"""
        if TYPE_CHECKING:
            target: str
            action: Literal["cron", "toggle", "preview", "edit", "delete", "one_shot"]
        target, action = data.args
        schedule = self.model["schedules"][target]

        self.show_spinner()
        match action:
            case "cron":
                # Lookup current cron expression in model and set dialog
                old_cron = schedule.cron
                self.cron_dialog.reset(old_cron)
                if (new_cron := await self.cron_dialog) is not None:
                    # Update model with new cron and refresh table
                    schedule.cron = CronStr(new_cron)
                    # Live-patch the schedule with the new cron string and
                    # set disabled
                    patch_data = ScheduleUpdate(is_enabled=False, cron=new_cron)  # type: ignore[call-arg]
                    await schedules.patch_schedule(schedule.id, patch_data)
                    schedule.is_enabled = False

            case "toggle":
                schedule.is_enabled = not schedule.is_enabled
                # Live-patch the schedule with the enable state
                patch_data = ScheduleUpdate(is_enabled=schedule.is_enabled)  # type: ignore[call-arg]
                await schedules.patch_schedule(schedule.id, patch_data)

            case "preview":
                if schedule.id != self.model["active_schedule"]:
                    self.model["active_templates"] = [
                        t async for t in schedules.get_schedule_templates(schedule_id=schedule.id)
                    ]
                scheduler_preview = ScheduleReviewDialog(
                    dialog_title=schedule.name,
                    schedule=schedule.model_dump(),
                    templates=self.model["active_templates"],
                )
                await scheduler_preview
                scheduler_preview.clear()

            case "edit":
                # stash the PAGE schedule model in CLIENT storage so we can
                # "import" it in a campaign edit page
                app.storage.tab["schedule"] = schedule
                ui.navigate.to(f"/schedules/{schedule.id}")

            case "delete":
                confirm = ConfirmationDialog(
                    icon="delete",
                    message="""\
                        Deleting a schedule removes it and all its manifest templates from the application.
                        This is irreversable and permanent.
                        You might want to "edit" the schedule first and "export" a backup first.

                        Are you sure?
                    """,
                    show_remember_checkbox=False,
                )
                go_for_it, _ = await confirm
                confirm.clear()
                if go_for_it:
                    _ = self.model["schedules"].pop(target, None)
                    await schedules.delete_schedule(schedule.id)
                    ui.notify("Schedule deleted", color="warning")

            case "one_shot":
                await schedules.oneshot_schedule(schedule.id)
                confirm = ConfirmationDialog(
                    icon="done",
                    icon_color="positive",
                    message="""\
                        The schedule has been executed as a one-shot. If this was successful, you may
                        navigate to the campaign overview page or stay here.
                    """,
                    yes_button_label="Navigate",
                    no_button_label="Stay",
                    show_remember_checkbox=False,
                )
                stay_or_go, _ = await confirm
                confirm.clear()
                if stay_or_go is True:
                    # we don't actually know the name or the id of the campaign
                    # here, so the best we can do is navigate to the campaign
                    # overview page
                    ui.navigate.to("/")

            case _ as unreachable:
                assert_never(unreachable)

        await self.update_table_rows()
        self.hide_spinner()

    async def handle_starts_after_picker(self, data: ClickEventArguments) -> None:
        """Callback for starts-after filter button, applies a chosen datetime
        to the page model.
        """
        dt_picker = DatetimePickerDialog(
            self.model["active_starts_after_filter"].timestamp(),
            dialog_title="Show Schedules Starting After...",
        )
        result: datetime | None = await dt_picker
        dt_picker.clear()
        if result is not None:
            self.model["active_starts_after_filter"] = result
            await self.update_table_rows()

    async def update_table_rows(self) -> None:
        """Replace the page table's rows with a new set.

        Note: This function does not re-acquire details from the API, it builds
        the rows from the current state of the page model.
        """
        # TODO this method should access the API, and the filtering should be
        # pushed to the API via query params
        self.schedules_table.rows = [
            {
                "id": schedule.id,
                "name": schedule.name,
                "cron": schedule.cron,
                "status": schedule.is_enabled,
                "owner": schedule.metadata_["owner"],
                "next": schedule.cron.next_run,
                "actions": None,
                "classes": "",
                "cron_extra": schedule.metadata_.get("dirty", {}).get("cron", ""),
                "status_extra": schedule.metadata_.get("dirty", {}).get("status", ""),
            }
            for schedule in sorted(
                self.model["schedules"].values(),
                key=lambda x: (x.next_run_at is None, x.next_run_at),
                reverse=False,
            )
            if self.apply_row_filter(schedule)
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
            ui.markdown("""\
            ## Scheduling Tips
            - If you change the cron expression for a schedule, the schedule will be automatically disabled.
            - All schedule times are displayed and processed in UTC.
            - Any campaign can be turned into a schedule by enabling Scheduling Mode from the Campaign Edit page.
            - Only whitelisted Python modules can be used in variable template expressions.
            - "One-shotting" a schedule sets it up for execution in the CM Service Daemon, for which there may be some time lag.
            """)  # noqa: E501

    def apply_row_filter(self, schedule: CreateSchedule) -> bool:
        """Compare a schedule against the page's active filters."""
        passes_filter = False

        # if no owner filter value applied, ignore filter
        if not self.owner_filter.value:
            passes_filter = True
        elif schedule.metadata_["owner"] in self.owner_filter.value:
            passes_filter = True
        # else still false

        # FIXME the starts_after filter is always active
        # pass if the schedule has a next run date after the filter
        if (
            schedule.next_run_at is not None
            and schedule.next_run_at >= self.model["active_starts_after_filter"]
        ):
            passes_filter = True
        elif schedule.cron.next_after() >= self.model["active_starts_after_filter"]:
            passes_filter = True
        else:
            passes_filter = False

        return passes_filter
