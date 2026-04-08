# ruff: disable[ERA001, W505]

from typing import Any, Self, assert_never

from httpx import AsyncClient
from nicegui import run, ui
from nicegui.events import GenericEventArguments
from pydantic_extra_types.cron import CronStr

from ..api.schedules import get_schedule_summary
from ..components import storage
from .common import CMPage, CMPageModel


class ScheduleOverviewPageModel(CMPageModel):
    schedules: list[dict[str, Any]]


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
            "schedules": [],
        }
        storage.initialize_client_storage()
        # client_state: storage.ClientStorageModel = app.storage.client["state"]

        # Default filters
        # active_filters = app.storage.client["state"].user.active_filters
        # active_filters.add("ignored")
        # app.storage.client["state"].user.active_filters = active_filters

        async for schedule in await run.io_bound(get_schedule_summary, client=client_):
            # TODO check favorites / filters
            self.model["schedules"].append(schedule)

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
            {"name": "name", "label": "Name", "field": "name", "sortable": True},
            {"name": "owner", "label": "Owner", "field": "owner", "sortable": True},
            {"name": "cron", "label": "Cron Expression", "field": "cron", "sortable": False},
            {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "center"},
            {"name": "next", "label": "Next Run", "field": "next", "sortable": True},
            {"name": "actions", "label": "Actions", "field": "actions"},
        ]
        rows: list[dict[str, Any]] = [
            {
                "id": schedule["id"],
                "name": schedule["name"],
                "cron": schedule["cron"],
                "status": schedule["is_enabled"],
                "owner": schedule["metadata"]["owner"],
                "next": CronStr(schedule["cron"]).next_run,
                "actions": None,
            }
            for schedule in sorted(
                self.model["schedules"], key=lambda x: x.get("next_run_at", 0), reverse=False
            )
        ]
        with self.table_content:
            schedules_table = ui.table(columns=columns, rows=rows).classes("w-full h-full overflow-auto")

        with schedules_table.add_slot("body-cell-actions"):
            with schedules_table.cell("actions"):
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
        match data:
            case GenericEventArguments():
                # Only for emit handlers
                target, action = data.args
            case _ as unreachable:
                assert_never(unreachable)
        ui.notify(f"{action}: {target}")

    async def new_schedule_controls(self):
        with ui.element("div").classes("w-full h-full pt-[0.5rem] pb-[0.5rem] overflow-y-auto"):
            ui.label("Add a new schedule")
